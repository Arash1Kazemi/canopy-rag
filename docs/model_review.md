# Review of offline candidate models

Project: offline hierarchical RAG core for organizational knowledge management, issue management, and knowledge transfer.
Source: step 1 of Phase 2, chapter 4 of "AI Engineering" (the model selection workflow), and the model pages listed at the end. Status: draft. Facts were read on 2026-10-26.

## What this step decides

Which small local models we will run in Phase 2: one group for embeddings, one for the LLM, and one for the LVM. It does not pick a winner. It builds a short list that fits this laptop, and the experiments in `docs/prompt_test_plan.md` choose among them. The full table is `models/model_registry.csv`.

## The method: the book's four steps

Chapter 4 splits model choice into four steps, and says the steps repeat.

| Step in the book | What we did |
|---|---|
| 1. Filter out models whose hard attributes do not work | Fixed our hard attributes (below) and dropped what breaks them |
| 2. Use public information to narrow the list | Read each model's page and card, and estimated memory use |
| 3. Run experiments with your own evaluation pipeline | Planned in `docs/prompt_test_plan.md` and run after the download is approved |
| 4. Monitor in production | Not relevant yet |

The book separates **hard attributes**, which you cannot or will not change, from **soft attributes**, which tuning can improve. Ours:

| Hard attributes (filter) | Soft attributes (measure) |
|---|---|
| Runs fully offline after the download | Answer correctness and citations |
| Fits this laptop: 4 GB GPU, about 15 GB RAM | Speed and memory use |
| A licence we can use for a university project | Follows the "insufficient knowledge" rule |
| Runs through a local runtime with an HTTP interface on this machine | Reads a scanned page |
| English now, with Persian kept possible for later | How much a better prompt helps |

## This laptop

| Part | Reading |
|---|---|
| CPU | AMD Ryzen 7 6800H, 8 cores, 16 threads |
| RAM | 15.3 GB |
| GPU | NVIDIA GeForce RTX 3050 Laptop, 4096 MiB, of which 1168 MiB was already used by Windows |
| Free disk | 50.8 GB on E: and 33.6 GB on C: |

The usable GPU memory is therefore about 2.9 GB. The model has to share it with its working memory, and what does not fit is run on the CPU, which is slower but works because the RAM is 15.3 GB.

## The memory rule

Chapter 7 of the book gives a rough formula: the memory a model needs to answer is its weights times 1.2, where the extra 20 percent is the working memory. In words: the file you download is about the size of the weights, so multiply it by 1.2. Example: `qwen3:4b` is a 2.5 GB download, so it needs about 3.0 GB, which is a little more than the 2.9 GB free, so part of it runs on the CPU. The book says the 20 percent grows with a longer context, so we keep the context short and measure the real use (metric M25) instead of trusting the formula.

## Embedding models

An embedding model turns text into a list of numbers so that texts with a similar meaning get close lists. It must be small and fast, because it runs on every chunk and every question.

| Model | Download | Why it is on the list | Watch out for |
|---|---|---|---|
| `nomic-embed-text` | 0.27 GB | Smallest. Very widely used. | Needs the prefixes `search_query:` and `search_document:`, and the Ollama page does not say so. English only. |
| `embeddinggemma:300m` | 0.62 GB | Small, 100+ languages | Different prefixes for queries and documents. 2K context. |
| `qwen3-embedding:0.6b` | 0.64 GB | 100+ languages, long context, Apache-2.0 | A query needs a one-line task instruction. |
| `bge-m3` | 1.2 GB | The multilingual reserve, no query instruction needed | Biggest of the group. Second download tier. |
| `qwen3-embedding:4b` | 2.5 GB | Shows what a bigger model could add | Does not fit the free GPU memory. Not run. |

We shortlist the first three. Search results ranked embedding models with benchmark scores, but those pages were commercial blogs that did not agree with each other, so we do not use their scores to choose. Our own retrieval metrics (M06 to M08) decide.

## LLMs

The LLM answers from the retrieved chunks, so it does not need to know facts. It needs to follow the rules: use only the documents, cite the file, and say "insufficient knowledge" when the answer is missing.

| Model | Download | Why it is on the list | Watch out for |
|---|---|---|---|
| `qwen3:1.7b` | 1.4 GB | The small end: shows how little model can work | Thinking mode is on by default |
| `qwen3:4b` | 2.5 GB | A strong small general model, Apache-2.0 | Part of it runs on the CPU. Thinking mode is on by default. |
| `phi4-mini:3.8b` | 2.5 GB | MIT licence, strong reasoning for its size | Its card says it holds little factual knowledge, which suits RAG, and it is weaker outside English. |
| `llama3.2:3b` | 2.0 GB | A common reference model, fits the GPU | The licence needs the notice "Built with Llama". Persian is not a listed language. |
| `qwen3.5:2b` | 2.7 GB | Newest family, takes images, so one model might do both jobs | New: little independent evidence yet. |
| `gemma3:4b`, `gemma4:e2b` | 3.4 and 4.6 GB | Strong families | Bigger than the free GPU memory. Not run in the first baseline. |

## LVMs

The LVM reads page images. Its one job in this project is to turn a scanned page, such as D19, into text that the rest of the system can index.

| Model | Download | Why it is on the list | Watch out for |
|---|---|---|---|
| `qwen3-vl:2b` | 1.9 GB | General vision model, with OCR improvements noted on its card | The Ollama page needs a recent Ollama |
| `glm-ocr:q8_0` | 1.8 GB | A 0.9B model built only for reading documents | It is not a chat model: the prompt must start with `Text Recognition:` |
| `qwen2.5vl:3b`, `granite3.2-vision:2b`, `moondream:1.8b` | 3.2, 2.4 and 1.7 GB | Common small vision models | `moondream` has a 2K context and its page does not mention OCR. Not run in the first baseline. |

## The runtime

We need something that loads a model and answers on `127.0.0.1`. We choose **Ollama**, in its standalone form.

| Fact (read on the Ollama release page and docs) | Why it matters |
|---|---|
| The release `v0.40.11` has `ollama-windows-amd64.zip`, 1586 MB, "containing only the Ollama CLI and GPU library dependencies for Nvidia" | One folder that we start ourselves with `ollama serve`. There is no installer step. |
| The same release has `OllamaSetup.exe`, 1662 MB | The docs say the installer leaves Ollama running in the background and helps keep it up to date, which we do not want on an offline project |
| The API is at `http://127.0.0.1:11500` (not the default 11434, which Windows reserved on this laptop), with `/api/embed` and `/api/chat`, and the chat reply reports its own timings in nanoseconds | We get speed numbers (M22, M23) with no extra tool |
| Models are stored in the folder named by `OLLAMA_MODELS` | We keep the models on E:, next to the project, and set the variable only for the server process |
| `ollama ps` shows how much of a loaded model is on the GPU and how much on the CPU | We can see and record the offload |

llama.cpp and LM Studio are other ways to run these models. We did not evaluate them. Ollama is enough for this phase, and the code talks to it only through one small client, so it can be replaced.

## What we do not know yet, and which experiment answers it

| Question | Answered by |
|---|---|
| Which embedding model finds the right chunk most often? | E1 |
| How much does the LLM matter once retrieval is right? | E2, with the right chunks given to the model |
| Does each LLM say "insufficient knowledge" instead of guessing? | E3 |
| Can a 2B vision model read a scanned meeting minute exactly? | E4 |
| Can a small model judge answers consistently? | E5 |
| What are the real speed and memory numbers with partial CPU offload? | E6 |

## Limits of this review

- The facts come from model pages and cards on 2026-10-26. A page can change.
- The book was written in 2024. Its method of choosing a model is still sound, but it does not know these models. Qwen3.5 and Gemma 4 appeared after it.
- The Ollama pages show a download size, not the memory use. M25 measures that.
- Licences for several rows say `not checked`. Check them before using a model outside the university.

## Sources

- Ollama model pages: https://ollama.com/library/nomic-embed-text , https://ollama.com/library/embeddinggemma , https://ollama.com/library/qwen3-embedding , https://ollama.com/library/bge-m3 , https://ollama.com/library/qwen3 , https://ollama.com/library/phi4-mini , https://ollama.com/library/llama3.2 , https://ollama.com/library/qwen3.5 , https://ollama.com/library/gemma3 , https://ollama.com/library/gemma4 , https://ollama.com/library/qwen3-vl , https://ollama.com/library/glm-ocr , https://ollama.com/library/qwen2.5vl , https://ollama.com/library/granite3.2-vision , https://ollama.com/library/moondream
- Model cards: https://huggingface.co/nomic-ai/nomic-embed-text-v1.5 , https://huggingface.co/google/embeddinggemma-300m , https://huggingface.co/Qwen/Qwen3-Embedding-0.6B , https://huggingface.co/BAAI/bge-m3 , https://huggingface.co/Qwen/Qwen3-4B , https://huggingface.co/Qwen/Qwen3-1.7B , https://huggingface.co/microsoft/Phi-4-mini-instruct , https://huggingface.co/meta-llama/Llama-3.2-3B-Instruct , https://huggingface.co/Qwen/Qwen3.5-2B , https://huggingface.co/Qwen/Qwen3-VL-2B-Instruct , https://huggingface.co/zai-org/GLM-OCR
- Ollama docs and release: https://docs.ollama.com/windows , https://docs.ollama.com/api/chat , https://docs.ollama.com/api/embed , https://docs.ollama.com/context-length , https://github.com/ollama/ollama/releases
