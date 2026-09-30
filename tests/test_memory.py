from harness import Agent, InMemoryMemory


def test_memory_operations_and_isolation() -> None:
    memory = InMemoryMemory()
    assert memory.get("absent") is None
    assert memory.get("absent", "fallback") == "fallback"
    memory.set("value", 1)
    memory.set("value", 2)
    assert memory.get("value") == 2
    assert InMemoryMemory().get("value") is None
    memory.delete("value")
    memory.delete("absent")
    assert memory.get("value") is None


def test_reset_preserves_memory() -> None:
    memory = InMemoryMemory()
    agent = Agent("fake/model", memory=memory)
    memory.set("project", "demo")
    agent.reset()
    assert agent.memory.get("project") == "demo"
