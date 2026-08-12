# Async SDK Usage

!!! warning "Not yet implemented"
    Async SDK methods are **not yet implemented**. There are currently no `acomplete`, `aask`, `aingest`, `aask_stream`, or async session methods on `crp.SDKClient`.

The sections below describe the planned async surface once it is wired.

---

## Planned async client

```python
import asyncio
import crp

async def main():
    client = crp.SDKClient()

    r = await client.acomplete("Summarise the EU AI Act")
    print(r.text)
    print(r.crp.risk)

asyncio.run(main())
```

---

## Planned async `ask()` and streaming

```python
async def ask_question():
    client = crp.SDKClient()
    a = await client.aask("Write a deployment guide")
    print(a.text)
    print(a.sources)

async def stream_question():
    client = crp.SDKClient()
    async for chunk in client.aask_stream("Write a deployment guide"):
        print(chunk.text, end="")
```

---

## Planned async ingestion

```python
async def ingest_docs():
    client = crp.SDKClient()
    await client.aingest("./docs/")
    print(client.storage.fact_count())
```

---

## Planned async sessions

```python
async def chat():
    client = crp.SDKClient()
    # Planned: client.asession() or session async methods
    r1 = await client.aask("What is the EU AI Act?")
    r2 = await client.aask("Which articles apply to high-risk systems?")
```

---

## Concurrency tips

- Create one `crp.SDKClient` per process and share it across tasks. The client holds one session handle internally.
- For multi-tenant services, instantiate separate clients per tenant or wait for explicit `session_id=` support.
