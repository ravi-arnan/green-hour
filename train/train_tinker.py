#!/usr/bin/env python3
"""Fine-tune an open-weight model on Green Hour's field notes, via Tinker.

This is the technical centrepiece: take a small open-weight model and make
it good at *one* narrow job — reading a messy walk transcript and emitting a
clean ``FieldEntry`` — well enough to beat a much larger general model at it.

Tinker handles the distributed training; this script only builds the data
and drives the loop. Loss is applied to the completion tokens only, so the
model learns to produce the JSON, not to reproduce the prompt.

    uv run --with-requirements train/requirements.txt \\
        train/train_tinker.py --steps 300

Prints a loss trace and, at the end, the sampling checkpoint path to put in
``TINKER_MODEL_PATH`` (and a playground URL to eyeball it).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import pathlib
import random
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "_lib"))

from greenhour.models import SYSTEM_PROMPT  # noqa: E402


def load_records(path: pathlib.Path) -> list[dict]:
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            records.append(json.loads(line))
    if not records:
        raise SystemExit(f"no training records in {path}; run build_dataset.py first")
    return records


def build_datum(types, tokenizer, record: dict):
    conversation = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                "Voice note transcript:\n"
                f'"""\n{record["transcript"]}\n"""\n\n'
                "Return one JSON object matching the schema."
            ),
        },
    ]
    try:
        prompt_tokens = tokenizer.apply_chat_template(
            conversation=conversation,
            add_generation_prompt=True,
            return_dict=False,
            enable_thinking=False,
        )
    except TypeError:
        prompt_tokens = tokenizer.apply_chat_template(
            conversation=conversation,
            add_generation_prompt=True,
            return_dict=False,
        )
    completion_tokens = tokenizer.encode(
        json.dumps(record["entry"], ensure_ascii=False, sort_keys=True)
    )

    full = list(prompt_tokens) + list(completion_tokens)
    weights = [0.0] * (len(prompt_tokens) - 1) + [1.0] * len(completion_tokens)
    return types.Datum(
        model_input=types.ModelInput.from_ints(full[:-1]),
        loss_fn_inputs={
            "weights": weights,
            "target_tokens": full[1:],
        },
    )


async def train(args: argparse.Namespace) -> int:
    import tinker
    from tinker import types

    records = load_records(args.data)
    rng = random.Random(args.seed)
    rng.shuffle(records)
    if args.max_examples:
        records = records[: args.max_examples]

    service = tinker.ServiceClient()
    training = await service.create_lora_training_client_async(
        base_model=args.base_model, rank=args.rank
    )
    tokenizer = training.get_tokenizer()

    print(
        f"training {args.base_model} (LoRA rank {args.rank}) "
        f"for {args.steps} steps on {len(records)} examples"
    )

    cursor = 0
    losses: list[float] = []
    for step in range(1, args.steps + 1):
        batch = [records[(cursor + i) % len(records)] for i in range(args.batch_size)]
        cursor += args.batch_size
        datums = [build_datum(types, tokenizer, record) for record in batch]

        fwd_bwd = await training.forward_backward_async(
            data=datums, loss_fn="cross_entropy"
        )
        optim = await training.optim_step_async(
            types.AdamParams(learning_rate=args.lr)
        )
        result = await fwd_bwd.result_async()
        await optim.result_async()

        loss = float(getattr(result, "loss", float("nan")))
        losses.append(loss)
        if step % args.log_every == 0 or step == 1:
            recent = losses[-args.log_every :]
            print(f"step {step:>5}  loss {loss:.4f}  avg{len(recent)} {sum(recent)/len(recent):.4f}")

    checkpoint = await training.save_weights_for_sampler_async(
        name=args.checkpoint_name
    )
    print("\ndone.")
    print(f"TINKER_MODEL_PATH={checkpoint.path}")
    try:
        print(f"playground: {checkpoint.get_playground_url()}")
    except Exception:  # noqa: BLE001 - optional convenience
        pass
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Tinker LoRA fine-tune for Green Hour.")
    parser.add_argument("--base-model", default="Qwen/Qwen3.5-4B")
    parser.add_argument("--rank", type=int, default=16)
    parser.add_argument("--lr", type=float, default=1e-4)
    parser.add_argument("--steps", type=int, default=300)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--max-examples", type=int, default=0)
    parser.add_argument("--log-every", type=int, default=10)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--checkpoint-name", default="green-hour-extractor")
    parser.add_argument(
        "--data", type=pathlib.Path, default=ROOT / "train" / "data" / "train.jsonl"
    )
    args = parser.parse_args()
    return asyncio.run(train(args))


if __name__ == "__main__":
    raise SystemExit(main())
