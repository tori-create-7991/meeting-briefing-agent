import os

from google.adk.memory import InMemoryMemoryService


def get_memory_service():
    """Factory for the ADK memory service backend.

    This is the swap point for wiring in Vertex AI Agent Engine's
    VertexAiMemoryBankService (past-meeting-trend context) in a future
    milestone — swap the MEMORY_BACKEND env var without restructuring
    callers.
    """
    backend = os.getenv("MEMORY_BACKEND", "in_memory")
    if backend == "in_memory":
        return InMemoryMemoryService()
    if backend == "vertex_memory_bank":
        raise NotImplementedError(
            "vertex_memory_bank backend is not wired yet — planned for a "
            "future milestone (Agent Engine Memory Bank integration)."
        )
    raise ValueError(f"Unknown MEMORY_BACKEND: {backend!r}")
