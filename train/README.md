# Fine-tuning Green Hour's extractor

The extractor turns a messy walk transcript into one `FieldEntry`. It is the
one place fine-tuning pays off: the job is narrow, the output shape is fixed,
and a small open-weight model can match a much larger general model at it for
a fraction of the latency and cost.

Everything here runs with [`uv`](https://docs.astral.sh/uv/) on a normal
machine — no GPU, no local inference. Tinker does the training on its side.
Use Python 3.12 (3.14 is too new for several ML wheels).

## Setup

```bash
export TINKER_API_KEY=...        # tinker.thinkingmachines.ai
export OPENROUTER_API_KEY=...    # for the baseline in eval.py
export GREENHOUR_TZ=Pacific/Auckland
```

## Run

```bash
# 1. Build the dataset (deterministic; ~500 examples, 78% outdoor).
uv run --with-requirements train/requirements.txt train/build_dataset.py --n 500

# 2. Fine-tune a LoRA adapter. Prints TINKER_MODEL_PATH when done.
uv run --with-requirements train/requirements.txt \
    train/train_tinker.py --base-model Qwen/Qwen3.5-4B --rank 16 --steps 300

# 3. Compare against the baseline on the held-out split.
uv run --with-requirements train/requirements.txt train/eval.py
```

Point the running agent at the adapter by setting `TINKER_MODEL_PATH` to the
value from step 2. `log-outside` picks it up automatically (`--backend auto`),
and falls back to OpenRouter if Tinker is unreachable.

## What the numbers mean

`eval.py` reports, per backend:

| metric | why it matters |
|---|---|
| schema-valid rate | can the caller trust the output without a retry? |
| outdoors accuracy | the only field the streak depends on |
| species F1 | the interesting field; set overlap, order-insensitive |
| notable F1 | same, for "what you noticed" |
| latency (ms) | a walk log should feel instant |
| output tokens | the cost proxy; small models emit tighter JSON |

The post quotes the base-versus-tuned row. Reproduce it with the commands
above and the same seed (`--seed 7`).
