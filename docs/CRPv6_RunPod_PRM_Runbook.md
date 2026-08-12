# CRPv6 Phase A — RunPod: Full PRM Training (exact instructions)

**Goal:** retrain `AutoCyberAI/crp-prm-deberta-v1` as DeBERTa-v3-**large** on the
full 5-source mix (~400k step examples). Four CPU-scale attempts failed the
gate; this is the 50×-data decisive run.

**Ship gate:** AUC ≥ 0.85 on held-out prm800k steps AND curated ≥ 8/10.
The test command in §6 prints both, plus per-example verdicts.

---

## 1. Files to upload (exactly two, self-contained)

From `C:\Users\User\Desktop\context-relay-protocol\scripts\`:

| File | Purpose |
|---|---|
| `train_crp_prm.py` | the trainer (imports only `datasets`/`transformers` — nothing else from the repo) |
| `eval_crp_prm.py` | the test harness (imports `_expand_record` from `train_crp_prm.py` in the same folder, `sklearn`, `datasets`) |

Upload them to **`/workspace/`** (the network volume mount point). Any of these works:

- JupyterLab file browser → Upload button (drag both files in), or
- `scp -P <ssh_port> scripts/train_crp_prm.py scripts/eval_crp_prm.py root@<pod_ip>:/workspace/`

Verify they landed: `ls -la /workspace/*.py`

## 2. Pod configuration (exact)

- **GPU:** RTX 4090 (24GB) ×1 — ~$0.69/h, total run ≈ **$4–7**
- **Template:** `RunPod Pytorch 2.4+ (CUDA 12.x)` — torch is PREINSTALLED
- **Volume:** your network volume mounted at `/workspace`
- **Container disk:** ≥ 40 GB is enough (volume holds everything important)

## 3. Environment setup (exact, verified versions)

Open the **Web Terminal** (or JupyterLab → Terminal) and run:

```bash
cd /workspace

# Do NOT reinstall torch — the template ships a working CUDA build.
python -c "import torch; print('torch', torch.__version__, '| cuda:', torch.cuda.is_available())"
# MUST print: cuda: True   — if False, you picked the wrong template; redeploy.

pip install --upgrade pip
pip install "transformers==4.57.6" "datasets==5.0.0" "accelerate>=1.0" \
    "pyarrow>=15" sentencepiece protobuf scikit-learn huggingface_hub

# Hugging Face WRITE token (required for the automatic push at the end):
hf auth login
```

These are the exact versions the pipeline was verified with locally. No
setfit / sentence-transformers needed — this run is DeBERTa only.

Point all caches and outputs at the network volume (survives pod restarts):

```bash
export HF_HOME=/workspace/.hf_cache
```

## 4. Launch training (visible progress, no tmux)

```bash
cd /workspace
python train_crp_prm.py \
    --base_model microsoft/deberta-v3-large \
    --output_dir /workspace/crp-prm-deberta-v1 \
    --push_to_hub AutoCyberAI/crp-prm-deberta-v1 \
    --datasets prm800k,math_shepherd,mmlu_pro,rlhflow_mistral,agentic_synth \
    --max_records 100000 \
    --max_train_examples 400000 \
    --target_invalid_share 0.40 \
    --agentic_samples 20000 \
    --eval_samples 60 \
    --max_eval_examples 2000 \
    --num_epochs 2 \
    --batch_size 32 \
    --learning_rate 1e-5 \
    --max_length 384 \
    --bf16 \
    --gradient_checkpointing \
    --num_workers 4 \
    --tokenize_workers 8 \
    2>&1 | tee /workspace/prm_train.log
```

**What you will see, in order:**

1. `INFO: Loading trl-lib/prm800k...` → `MMLU-Pro...` → `RLHFlow...` (~30–60 min
   data prep: downloads ~2 GB, parses ~1M records)
2. `INFO: Rebalancing: INVALID ...` and `INFO: Step-level examples: train=400000, eval=...`
3. A live tqdm bar: `NNN/25000 [elapsed<remaining, X.XXs/it]` plus a training
   loss line every 50 steps, e.g. `{'loss': 0.42, 'learning_rate': ..., 'epoch': 0.3}`
   — **loss should trend from ~0.6 down toward ~0.2**
4. `{'eval_loss': ...}` at each epoch end (2 epochs, ~25k steps total,
   **~5–7.5 h on a 4090**)
5. `INFO: Calibrated threshold 0.XXX (INVALID F1 ..., INVALID recall ..., VALID recall ...)`
6. Upload progress bars → `INFO: Done. Set CRP_PRM_MODEL=...`

Keep the browser tab open; if the connection drops the pod process dies.
If you must close it, use this one-liner instead (still no tmux) and watch with
`tail -f /workspace/prm_train.log`:

```bash
nohup python train_crp_prm.py ... (same args) > /workspace/prm_train.log 2>&1 &
```

Second terminal for GPU saturation check (should be >90% during training):

```bash
watch -n 5 nvidia-smi
```

## 5. OOM fallback (only if you see CUDA out of memory)

Restart with `--batch_size 16 --gradient_checkpointing` (rest is identical).
Checkpoints save per epoch, so an interrupted run can be pushed from the last
`checkpoint-*` directory if needed.

## 6. Test ON THE POD (visible results, ~10 min)

The training script calibrates and prints a threshold, but the independent
verdict comes from the eval harness — run it against the **local artifact**
immediately after training:

```bash
cd /workspace
python eval_crp_prm.py \
    --model /workspace/crp-prm-deberta-v1 \
    --eval_start 500 --eval_samples 60 \
    --no-nli_baseline
```

**You will see:**

```
=== Tier 1: held-out prm800k steps (1327) ===
Majority-class baseline: 0.9699
CRP PRM (...):  X.XXXX          <- want >= 0.97 AND real INVALID recall
              precision    recall  f1-score
     INVALID    ...      >=0.60   ...        <- the metric that failed 4x
       VALID    ...      >=0.90   ...

=== Tier 2: curated reasoning cases ===
[OK ] expected=VALID    ...     <- want 8/10 or better
```

Plus a quick AUC printout if you want it: the harness reports per-class
recall; the gate is **INVALID recall ≥ 0.60 with VALID recall ≥ 0.90 and
curated ≥ 8/10**.

## 7. Publish + teardown

If the gate passes: the model is already on the Hub (automatic push in step 4 —
check `https://huggingface.co/AutoCyberAI/crp-prm-deberta-v1`). The config
contains `prm_threshold` from calibration.

**Then terminate the pod immediately — idle pods bill by the hour.**
(The network volume keeps `prm_train.log` and `crp-prm-deberta-v1/`.)

If the gate fails: keep the volume artifacts, terminate the pod, and we wire
Skywork-o1-PRM-1.5B as the async PRM backend — Phase A still closes.

## 8. Troubleshooting

| Symptom | Fix |
|---|---|
| `cuda: False` in §3 | wrong template — redeploy with the CUDA PyTorch template |
| push fails 403 | token is read-only; create a **write** token, `hf auth login` again |
| slow dataset downloads | `pip install hf_transfer` then `export HF_HUB_ENABLE_HF_TRANSFER=1` and rerun |
| killed during tokenization | reduce `--tokenize_workers 4` |
| `ModuleNotFoundError: model_utils` in eval | you uploaded only one file — `eval_crp_prm.py` needs `train_crp_prm.py` beside it |

---

*Updated 2026-07-30: exact-file, exact-env, no-tmux edition with on-pod testing.*
