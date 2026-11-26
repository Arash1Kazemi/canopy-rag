"""The retrieval and answering commands of `python -m rag_core` (Phase 8D). __main__.py adds them with add_rag_commands.

    python -m rag_core index    [--db FILE] [--embedding qwen3-embedding-0.6b] [--policy words80] [--fake-models]
    python -m rag_core ask      --node N6 "question" [--db FILE] [--prompt P01|P13] [--k 3] [--llm phi4-mini] [--show-chunks]
    python -m rag_core evaluate [--run-id ID] [--prompt P01|P13] [--k 3] [--questions Q06,Q22] [--fake-models]

`index` ingests the case-study Markdown files into the database if it is empty, then embeds the chunks of the active
versions and stores the vectors (it runs again safely: a chunk that already has a vector is not embedded again).
`ask` retrieves inside one node, assembles the context, asks the model and prints the answer with its checked citations.
`evaluate` runs the 26 answer-key questions with the same settings as the Phase 2 baseline (qwen3-embedding-0.6b, phi4-mini,
words80, k=3, prompt P01), grades them with the Phase 2 grading code, and writes results/<run-id>/ in the baseline's
format plus a comparison against results/e3-first.

The real models run through Ollama on 127.0.0.1:11500 (H06). With --fake-models nothing is called: a hashing embedder
and a model that echoes the first chunk stand in, which tests the pipeline and nothing about answer quality.
Exit codes: 0 done (a refused question is a result, not an error), 2 the setup cannot work (Ollama not reachable or a model
not pulled, no index yet, an unknown node or model, a stale index, a results folder that already holds a run).
"""
import datetime as dt
import sys
from contextlib import ExitStack, closing
from pathlib import Path

from baseline_runner.ollama_api import OllamaClient, OllamaError

from .fakes import EchoLanguageModel, HashingEmbedder
from .infrastructure.ollama_embedding import DEFAULT_EMBEDDING_ID, ollama_url
from .infrastructure.project_db import database_path
from .infrastructure.sqlite import SqliteKnowledgeRepository
from .infrastructure.sqlite_vectors import SqliteVectorIndex
from .knowledge.chunking import DEFAULT_POLICY, POLICIES
from .knowledge.lifecycle import ChunkLifecycle
from .organization.directory import HierarchyNodeDirectory
from .rag.indexing import DEFAULT_BATCH_SIZE
from .rag.retrieval import DEFAULT_K
from .rag_wiring import load_hierarchy, make_retriever, prepare_case_study
from .shared.kernel import DomainError
from .workflows.answer_prompts import DEFAULT_ANSWER_PROMPT, load_answer_prompt
from .workflows.question_answering import QuestionService

PROJECT = Path(__file__).resolve().parent.parent
RESULTS = PROJECT / "results"
DEFAULT_LLM_ID = "phi4-mini"                 # the Phase 2 baseline LLM (models/model_registry.csv)
REFUSAL_WORDS = {
    "no_evidence": "nothing was retrieved that could be used, so the model was not asked",
    "context_too_small": "the best chunk did not fit the context budget, so the model was not asked",
    "model_refused": "the model said it does not have the knowledge",
    "no_valid_citation": "the model answered, but cited no file it was given (H09)",
}


class SetupError(Exception):
    """Something the user can fix before running again; the command prints it and exits with 2."""


def utc_now():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ------------------------------------------------------------------ the models (tests replace these functions)
def model_row(model_id):
    from baseline_runner.experiments import load_registry
    registry = load_registry()
    if model_id not in registry:
        raise SetupError(f"unknown model id {model_id!r}; the registry knows {sorted(registry)}")
    return registry[model_id]


def make_client():
    try:
        return OllamaClient(base_url=ollama_url())
    except ValueError as error:
        raise SetupError(str(error)) from error


def make_embedder(args):
    """The embedding model: a hashing fake, or qwen3-embedding (or another registry model) through local Ollama."""
    if args.fake_models:
        return HashingEmbedder()
    from .infrastructure.ollama_embedding import OllamaEmbeddingModel
    return OllamaEmbeddingModel(model_row(args.embedding)["runtime_tag"], args.embedding, client=make_client())


def make_language_model(args):
    """The language model: a fake that echoes the first chunk, or phi4-mini (or another registry model) through Ollama.
    The Phase 2 settings are kept (temperature 0, seed 42, 4096 context, 256 tokens): options={} adds nothing to them."""
    if args.fake_models:
        return EchoLanguageModel()
    from .infrastructure.ollama_language import OllamaLanguageModel
    row = model_row(args.llm)
    return OllamaLanguageModel(row["runtime_tag"], client=make_client(), options={},
                               think=False if row["thinking_listed"] == "yes" else None)


def server_info(args):
    """The server's version and pulled models (for meta.json), and a check that it can be reached at all."""
    if args.fake_models:
        return {"ollama_version": "fake", "pulled_models": {}}
    client = make_client()
    return {"ollama_version": client.version(), "pulled_models": client.models()}


def check_pulled(args, info, needs_llm):
    if args.fake_models:
        return
    missing = [tag for tag in (model_row(args.embedding)["runtime_tag"], model_row(args.llm)["runtime_tag"] if needs_llm else None)
               if tag and tag not in info["pulled_models"]]
    if missing:
        raise SetupError(f"not downloaded yet: {', '.join(missing)}. Pull them while online (docs/operator_guide.md, Part 2).")


def sampler_and_ps(args):
    if args.fake_models:
        return None, None
    from baseline_runner import system_info
    return system_info.snapshot, system_info.ollama_ps


# ------------------------------------------------------------------ index
def open_stores(db, stack):
    repository = stack.enter_context(closing(SqliteKnowledgeRepository(db)))
    index = stack.enter_context(closing(SqliteVectorIndex(db)))
    return repository, index


def cmd_index(args):
    db = Path(args.db) if args.db else database_path()
    hierarchy = load_hierarchy(args.hierarchy_db)
    embedder = make_embedder(args)
    with ExitStack() as stack:
        repository, index = open_stores(db, stack)
        _, ingested, report = prepare_case_study(repository, index, embedder, hierarchy, policy=args.policy, clock=utc_now,
                                                 lifecycle=ChunkLifecycle(), batch_size=args.batch_size)
    items = "ingested the case study" if ingested else "the database already held knowledge, so nothing was ingested"
    print(f"{items} ({db})")
    print(f"indexed {report.eligible} chunks of active versions: {report.embedded} embedded now in {report.batches} batches, "
          f"{report.kept} already indexed" + (", index rebuilt because the model or the policy changed" if report.rebuilt else ""))
    print(f"signature: embedding model {report.signature.embedding_model}, chunking policy {report.signature.chunking_policy}")
    return 0


# ------------------------------------------------------------------ ask
def print_result(result, show_chunks=False):
    answer = result.answer
    print(f"Question: {result.question}")
    print(f"Node {result.node_id}, k={result.k}, prompt {answer.prompt_id} (version {answer.prompt_version})")
    print("\nRetrieved (best first, this node only):")
    if not result.hits:
        print("  nothing")
    for hit in result.hits:
        used = "in context" if hit.chunk_id in answer.chunk_ids_used else "left out"
        print(f"  {hit.rank}. score {hit.score:.3f}  {hit.citation().render_long()}  ({used})")
        if show_chunks:
            print(f"     {hit.text}")
    print(f"\nContext: {len(answer.chunk_ids_used)} chunks given, {len(answer.chunk_ids_omitted)} left out, "
          f"about {answer.context_tokens} of {answer.budget_tokens} tokens; model {'called' if answer.model_called else 'not called'}")
    print(f"\nAnswer: {answer.text}")
    if answer.refused:
        print(f"\nRefused: yes, because {REFUSAL_WORDS[answer.refusal_reason]}")
    else:
        print("\nCitations (checked against the chunks that were given):")
        for citation in answer.citations:
            print(f"  {citation.render_long()}")
        if answer.invalid_citations:
            print(f"  removed from the answer, not in the context: {', '.join(answer.invalid_citations)}")
        if answer.uncited:
            print("  warning: the answer has no valid citation (kept because of --uncited mark)")
    return 0


def cmd_ask(args):
    db = Path(args.db) if args.db else database_path()
    if not db.is_file():
        raise SetupError(f"no database at {db}: run `python -m rag_core index --db {db}` first")
    hierarchy = load_hierarchy(args.hierarchy_db)
    HierarchyNodeDirectory(hierarchy).require(args.node)      # an unknown node is a setup error, before any model is called
    prompt = load_answer_prompt(args.prompt)
    with ExitStack() as stack:
        repository, index = open_stores(db, stack)
        if not index.chunk_ids():
            raise SetupError(f"the index in {db} is empty: run `python -m rag_core index --db {db}` first")
        embedder = make_embedder(args)
        model = make_language_model(args)
        service = QuestionService(make_retriever(index, embedder, hierarchy, repository), model, prompt,
                                  uncited_policy=args.uncited)
        return print_result(service.ask(args.question, args.node, args.k), args.show_chunks)


# ------------------------------------------------------------------ evaluate
def cmd_evaluate(args):
    from .evaluation import comparison_text, run_evaluation
    run_id = args.run_id or ("fake-" if args.fake_models else "core-") + dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    out = Path(args.out) if args.out else RESULTS / run_id
    if (out / "e3_rows.csv").exists():
        raise SetupError(f"{out} already holds a run; use another --run-id so no result is overwritten")
    prompt = load_answer_prompt(args.prompt)
    ids = {q.strip() for q in args.questions.split(",")} if args.questions else None
    info = server_info(args)                                   # fails first when Ollama is not reachable
    check_pulled(args, info, needs_llm=True)
    embedder, model = make_embedder(args), make_language_model(args)
    sampler, ps = sampler_and_ps(args)
    records, summary, rows = run_evaluation(
        out, embedder, model, prompt, llm_id=args.llm, embedding_id=args.embedding, chunks_name=args.policy, k=args.k,
        server_info=info, baseline_folder=Path(args.compare), question_ids=ids, sampler=sampler, ps=ps, clock=utc_now,
        hierarchy=load_hierarchy(args.hierarchy_db), uncited_policy=args.uncited)
    print()
    print(comparison_text(rows, args.compare, out.name))
    print(f"\nwritten: {out}")
    return 0


# ------------------------------------------------------------------ wiring
def guarded(run):
    """Run a command; a problem the user can fix prints one clear line and exits with 2, never a traceback."""
    def command(args):
        try:
            return run(args)
        except SetupError as error:
            print(f"error: {error}", file=sys.stderr)
        except OllamaError as error:
            print(f"error: the local model server cannot be used: {error}\n"
                  "Is Ollama running on 127.0.0.1:11500 (docs/operator_guide.md, Part 1)? "
                  "Add --fake-models to test the pipeline without a model.", file=sys.stderr)
        except DomainError as error:
            print(f"error: {error}", file=sys.stderr)
        except OSError as error:        # a timeout or a refused connection that was not wrapped
            print(f"error: cannot reach the local model server or read a file: {error}", file=sys.stderr)
        return 2
    return command


def add_rag_commands(sub):
    def common(p, llm):
        p.add_argument("--db", help="the database file that holds knowledge and vectors (default data/project.sqlite or RAG_DATA_DB)")
        p.add_argument("--hierarchy-db", help="read the hierarchy from this database instead of registry/node_layer_registry.csv")
        p.add_argument("--embedding", default=DEFAULT_EMBEDDING_ID, help="embedding model id (default qwen3-embedding-0.6b)")
        p.add_argument("--fake-models", action="store_true", help="no model, no network: a hashing embedder and an echo model")
        if llm:
            p.add_argument("--llm", default=DEFAULT_LLM_ID, help="language model id (default phi4-mini)")
            p.add_argument("--prompt", default=DEFAULT_ANSWER_PROMPT, choices=("P01", "P13"),
                           help="answer prompt: P01 is the Phase 2 prompt; P13 adds the conflict rule")
            p.add_argument("--uncited", default="refuse", choices=("refuse", "mark"),
                           help="an answer with no valid citation: refuse (default, H09) or mark")

    p = sub.add_parser("index", help="ingest the case study if needed, then embed and index the active chunks")
    common(p, llm=False)
    p.add_argument("--policy", default=DEFAULT_POLICY, choices=sorted(POLICIES), help="chunking policy (names the index signature)")
    p.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    p.set_defaults(run=guarded(cmd_index))

    p = sub.add_parser("ask", help="answer one question from one node's knowledge, with checked citations")
    common(p, llm=True)
    p.add_argument("question")
    p.add_argument("--node", required=True, help="the asking node, for example N6")
    p.add_argument("--k", type=int, default=DEFAULT_K, help="chunks to retrieve (default 3, the baseline)")
    p.add_argument("--show-chunks", action="store_true", help="print the text of each retrieved chunk")
    p.set_defaults(run=guarded(cmd_ask))

    p = sub.add_parser("evaluate", help="run the 26 answer-key questions through the core and compare with the baseline")
    common(p, llm=True)
    p.add_argument("--run-id", help="name of the results folder (default core-<date and time>)")
    p.add_argument("--out", help="the results folder (default results/<run-id>)")
    p.add_argument("--policy", default=DEFAULT_POLICY, choices=sorted(POLICIES), help="chunking policy (default words80, the baseline)")
    p.add_argument("--k", type=int, default=DEFAULT_K)
    p.add_argument("--questions", help="only these question ids, for example Q06,Q22 (the summary is then not comparable)")
    p.add_argument("--compare", default=str(RESULTS / "e3-first"), help="the baseline run to compare with (default results/e3-first)")
    p.set_defaults(run=guarded(cmd_evaluate))
