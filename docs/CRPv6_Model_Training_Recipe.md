# CRPv6 Model Training Guide

This guide gives exact, copy-pasteable commands to train the three optional ML models that CRPv6 can use:

1. **Intent / speech-act classifier** — SetFit model
2. **Process Reward Model (PRM)** — small DeBERTa step verifier
3. **Semantic-entropy NLI model** — off-the-shelf, with optional domain fine-tuning

All three are **optional**. CRP works without them because every managed model has a deterministic fallback. Once trained, you publish them to Hugging Face (or a private model registry) and point CRP at them with environment variables.

---

## 1. Intent / speech-act classifier (`CRP_INTENT_MODEL`)

### What it does

The managed intent classifier in `crp/isa/intent.py` loads a SetFit text-classification model and uses it to predict one of four CRP speech acts:

- `request`
- `question`
- `assertion`
- `expressive`

If the model is missing, slow, or raises, CRP falls back to a deterministic rule-based classifier.

### Training script

File: `scripts/train_crp_intent_setfit.py`

```bash
# 1. Install training dependencies
pip install setfit datasets huggingface_hub

# 2. Train locally (quick experiment)
python scripts/train_crp_intent_setfit.py \
    --base_model sentence-transformers/all-MiniLM-L6-v2 \
    --output_dir ./crp-intent-setfit \
    --max_samples 5000 \
    --num_epochs 1

# 3. Train and push to Hugging Face
python scripts/train_crp_intent_setfit.py \
    --base_model sentence-transformers/all-MiniLM-L6-v2 \
    --output_dir ./crp-intent-setfit \
    --push_to_hub YOUR_HF_USER/crp-intent-setfit \
    --max_samples 20000 \
    --num_epochs 3
```

### Datasets and links

| Resource | Link | Purpose |
|---|---|---|
| SetFit library | https://github.com/huggingface/setfit | Few-shot sentence-transformer training |
| Base encoder | https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2 | 22M parameter CPU-friendly encoder |
| Banking77 | https://huggingface.co/datasets/banking77 | Customer-service intents mapped to speech acts |
| SNIPS | https://huggingface.co/datasets/snips_built_in_intents | Voice-assistant intents mapped to speech acts |

### How the labels are produced

The script maps public intent labels to CRP speech acts heuristically, then mixes in synthetic templated examples. The final dataset has one label per example from the set `{request, question, assertion, expressive}`.

### Runtime usage

```bash
export CRP_INTENT_MODEL=YOUR_HF_USER/crp-intent-setfit
```

Or pass the local path:

```bash
export CRP_INTENT_MODEL=./crp-intent-setfit
```

---

## 2. Process Reward Model (`CRP_PRM_MODEL`)

### What it does

The PRM verifier in `crp/vr/prm.py` scores whether an intermediate reasoning step is entailed by / consistent with its premises. It is used by the Verification Relay (`crp/vr/`) when `depth` is `thorough` or `exhaustive`.

If the model is unavailable, the verifier returns `UNKNOWN` and the relay falls back to symbolic verifiers (Python execution, Z3) where available.

### Training script

File: `scripts/train_crp_prm.py`

```bash
# 1. Install training dependencies
pip install transformers datasets accelerate

# 2. Quick local experiment on 50k steps
python scripts/train_crp_prm.py \
    --base_model microsoft/deberta-v3-small \
    --output_dir ./crp-prm-deberta-v1 \
    --max_samples 50000 \
    --num_epochs 2 \
    --batch_size 16

# 3. Full train + push to Hugging Face
python scripts/train_crp_prm.py \
    --base_model microsoft/deberta-v3-small \
    --output_dir ./crp-prm-deberta-v1 \
    --push_to_hub YOUR_HF_USER/crp-prm-deberta-v1 \
    --num_epochs 3 \
    --batch_size 16
```

### Datasets and links

| Resource | Link | Purpose |
|---|---|---|
| PRM800K paper | https://arxiv.org/abs/2305.20050 | "Let's verify step by step" |
| Raw dataset | https://github.com/openai/prm800k | 800k step-level correctness labels |
| Processed HF dataset | https://huggingface.co/datasets/trl-lib/prm800k | Easiest form to load with `datasets` |
| Base model | https://huggingface.co/microsoft/deberta-v3-small | 44M parameter encoder |

### Label format

The script consumes the `trl-lib/prm800k` records and converts each step into a binary classification example:

```text
premises: <problem + prior steps> [SEP] step: <current step>
```

- `rating > 0` → `VALID`
- `rating <= 0` → `INVALID`

### Runtime usage

```bash
export CRP_PRM_MODEL=YOUR_HF_USER/crp-prm-deberta-v1
```

---

## 3. Semantic-entropy NLI model (`CRP_NLI_MODEL`)

### What it does

The semantic-entropy module in `crp/ep/semantic_entropy.py` clusters sampled answers by bidirectional entailment. An NLI model decides whether two answers mean the same thing. If the model is unavailable, CRP falls back to exact-string equality clustering.

### Default off-the-shelf model

You usually do **not** need to train this. The default model is already small and accurate:

- https://huggingface.co/cross-encoder/nli-deberta-v3-xsmall

Alternative binary entailment model:

- https://huggingface.co/MoritzLaurer/DeBERTa-v3-xsmall-mnli-fever-anli-ling-binary

### Optional fine-tuning

If you want a CRP-specific NLI model, fine-tune `cross-encoder/nli-deberta-v3-xsmall` on pairs extracted from your audit triples:

- `task + answer_a` vs `task + answer_b`
- Label = `ENTAILMENT` if both answers are correct and equivalent, otherwise `NOT_ENTAILMENT`

There is no dedicated training script yet; use the standard `sentence-transformers/cross-encoder` training template.

### Runtime usage

```bash
export CRP_NLI_MODEL=cross-encoder/nli-deberta-v3-xsmall
```

---

## 4. Coreference model (`CRP_COREF_MODEL`)

### What it does

`crp/isa/coref.py` resolves pronouns and deixis (`"it"`, `"that approach"`, `"the second option"`) against a session entity registry.

### Default model

Install `fastcoref` and CRP uses it automatically:

```bash
pip install fastcoref
```

Repository: https://github.com/shon-otmazgin/fastcoref

If `fastcoref` is not installed, CRP falls back to rule-based pronoun/ordinal replacement.

### Runtime usage

```bash
export CRP_COREF_MODEL=   # empty uses fastcoref default
```

---

## 5. Publishing checklist

Before you publish a model and flip the default in CRP:

1. **Benchmark it.** Run the SQB / safety / verification suites and confirm no regression versus the fallback path.
2. **Document the training data.** Include the dataset names, version, and any synthetic templates used.
3. **Include a model card.** State intended use, limitations, and the CRP fallback path.
4. **License check.** PRM800K is MIT. Banking77 and SNIPS have their own licences; verify commercial use is permitted.
5. **Pin the revision.** Use a specific model revision or tag in production configs, not `main`.

---

## 6. Environment-variable summary

| Model | Env var | Default placeholder |
|---|---|---|
| Intent / speech act | `CRP_INTENT_MODEL` | `AutoCyberAI/crp-intent-setfit` |
| PRM verifier | `CRP_PRM_MODEL` | `AutoCyberAI/crp-prm-deberta-v1` |
| Semantic-entropy NLI | `CRP_NLI_MODEL` | `cross-encoder/nli-deberta-v3-xsmall` |
| Coreference | `CRP_COREF_MODEL` | (fastcoref default) |
| ML device | `CRP_ML_DEVICE` | `auto` |
| ML cache dir | `CRP_ML_CACHE_DIR` | (none) |

---

## 7. Quick verification

After setting the env vars, run:

```bash
python -c "
import crp
from crp.isa import ManagedIntentClassifier
from crp.vr.prm import ProcessRewardVerifier
from crp.ep.semantic_entropy import semantic_entropy

tag = ManagedIntentClassifier().classify('What is the weather in Sydney?')
print('speech_act:', tag.speech_act)

print('entropy:', semantic_entropy(['22 °C sunny', '22 degrees and sunny', 'raining']))
"
```

If models are not present, you will still see output because the fallback paths activate automatically.
