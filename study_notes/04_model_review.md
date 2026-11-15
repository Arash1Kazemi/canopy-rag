# Note 4: review of the candidate models

Where we are: step 1. Book: chapter 2 (foundation models), chapter 4 (model selection workflow), chapter 7 (the memory formula).
Files made in this step: `docs/model_review.md`, `models/model_registry.csv`.

## In one minute

The system needs three kinds of local model, and your laptop (4 GB GPU, 15 GB RAM) rules out most of what exists. We read each candidate's page, estimated its memory with the book's rule, and shortlisted what fits. We did not pick a winner. The experiments do that, using your own 26 questions, because public rankings are written for other tasks.

## 1. The three kinds of model

| Kind | Job here | Analogy | Input and output |
|---|---|---|---|
| Embedding model | Finds which chunks are about the question | A librarian who places every page on a map of meaning, so pages about the same thing sit close together | Text in, a list of numbers out |
| LLM | Writes the answer from the chunks it is handed | A writer who may only use the pages on the desk | Text in, text out |
| LVM (vision-language model) | Reads a picture of a page | A reader who can look at a photograph of a page and type it out | Image and text in, text out |

A small LLM does not have to know the city's facts. It has to follow rules: use only the documents, cite the file, and say "insufficient knowledge" when the answer is not there. That is why small models are worth testing at all. The Phi-4-mini model card says exactly this about itself: it stores little factual knowledge, so it should be paired with retrieval.

## 2. How big is a model? Parameters, bytes, memory

A model is a very large table of numbers. Each number is a **parameter**. "4B" means four billion numbers. Each number is stored in some number of bytes, and the total is the memory the model needs.

- At 16 bits (2 bytes) per number, 4 billion numbers take 8 GB. The book's example: a 7B model at 2 bytes needs 14 GB.
- **Quantization** stores each number more coarsely, with fewer bits. Analogy: saving a photo as a smaller JPEG, or rounding every price to whole euros. The file shrinks a lot, and quality drops a little. A name like Q4 or Q8 means 4 or 8 bits per number.
- Working memory is on top. The book's rough rule: **memory ≈ the size of the weights × 1.2**. The extra 20 percent grows with a longer prompt, so treat it as a guide, and measure the real use (metric M25).

Your free GPU memory is about 2.9 GB (4096 MiB, minus 1168 MiB that Windows already uses).

| Model | Download | × 1.2 | Fits in 2.9 GB? |
|---|---:|---:|---|
| `nomic-embed-text` | 0.27 GB | 0.33 GB | yes |
| `embeddinggemma:300m` | 0.62 GB | 0.75 GB | yes |
| `qwen3-embedding:0.6b` | 0.64 GB | 0.77 GB | yes |
| `qwen3:1.7b` | 1.4 GB | 1.7 GB | yes |
| `glm-ocr:q8_0` | 1.8 GB | 2.2 GB | yes |
| `qwen3-vl:2b` | 1.9 GB | 2.3 GB | yes |
| `llama3.2:3b` | 2.0 GB | 2.4 GB | yes |
| `qwen3:4b` | 2.5 GB | 3.0 GB | slightly over |
| `phi4-mini:3.8b` | 2.5 GB | 3.0 GB | slightly over |
| `qwen3.5:2b` | 2.7 GB | 3.2 GB | over |
| `gemma3:4b` | 3.4 GB | 4.1 GB | no |

What "does not fit" means: the server puts as many layers as it can on the GPU, and runs the rest on the CPU. It still works, because you have 15.3 GB of RAM, but it is slower. `ollama ps` shows the split. So the short list includes models that are slightly over, and the speed metrics will show the price.

## 3. Reading a model card: a checklist

Every row of the registry came from a page, with a source and a date. For each model, find:

1. **Size and download.** The real number to plan with.
2. **Context length.** How much text it can read at once. Pages can disagree: for `qwen3:4b` the Ollama page says 256K and the original card says 32,768. We run with a small context anyway.
3. **Languages.** Phi-4-mini and Llama 3.2 do not list Persian. Our project is English now and Persian later, so this matters.
4. **Licence.** Gemma has its own terms. Llama 3.2 needs the notice "Built with Llama". Write `not checked` when you did not check. Never guess.
5. **Prompt format.** This is where cards surprise you. `nomic-embed-text` needs the prefixes `search_query:` and `search_document:`, and the Ollama page does not say so. `glm-ocr` needs the prompt to start with `Text Recognition:`.
6. **Thinking mode.** Qwen3 starts by writing a long hidden "thinking" text unless you switch it off. That makes it slower and its speed not comparable, so we set `think` to false.
7. **Limits the authors state.** Write them down.

## 4. The selection method from the book

Chapter 4 splits the choice into four steps, and says they repeat:

1. Filter out models whose **hard attributes** do not work for you. A hard attribute is something you cannot change: it must run offline, fit this laptop, have a usable licence.
2. Use public information to narrow the list. We read the pages and cards.
3. Run experiments with your own evaluation pipeline. This is the next step of Phase 2.
4. Monitor in production. Not relevant yet.

A **soft attribute** is one you can improve by effort: accuracy, a prompt, the chunking. The book gives an example where accuracy rose from about 20% to 70% by splitting a task in two, and another where a model stayed unusable after weeks of tuning. You find out only by trying.

## 5. Why we did not choose from rankings

The web results for "best small models" were commercial blogs. Some gave different sizes for the same model, and some had no stated method. The book (chapter 4) also warns that public benchmarks cannot be fully trusted for your own task, so you build your own pipeline with your own prompts and metrics. That is the whole point of your answer key and the metrics of Phase 1. A leaderboard score is a clue for step 2, never the decision.

## 6. The runtime

We need a program that loads a model and answers on this machine only. We chose Ollama in its standalone form: a zip of 1586 MB with only the command-line program and the NVIDIA libraries, so there is no installer and no tray app. We start it ourselves and keep the models on drive E:, where there is room. The installer would have kept itself updated in the background, which is not what an offline project wants.

## 7. Common mistakes

1. Choosing by the biggest number on the page. A bigger model that does not fit the laptop is slower than a smaller one that does.
2. Trusting one source. The same model had two different context lengths on two pages.
3. Forgetting the prompt format of an embedding model, then blaming the model for bad results.
4. Comparing models with thinking switched on for one and off for another.
5. Calling a model "bad" after one question. With 26 questions, wait for the pattern.

## 8. Check yourself

1. Will `gemma3:4b` (a 3.4 GB download) fit in your free GPU memory? What happens if it does not?
2. In one sentence: what is quantization, and what does it cost?
3. Why is "Persian is not listed" a note and not a reason to reject Phi-4-mini now?
4. Why set `think` to false?

Answers:

1. 3.4 × 1.2 ≈ 4.1 GB, which is more than 2.9 GB, so it does not fit. Part of it runs on the CPU, which works but is slower.
2. Storing each number with fewer bits so the model is smaller and faster, at a small cost in quality.
3. The project is English only for now, and the Phase 2 test is on English questions. Persian is a later phase, and the registry keeps a reserve (`bge-m3`).
4. So the models are compared on the same footing. A thinking model writes a long hidden text first, which costs time and can use up the reply limit.
