"""The contract board stays at three open contracts."""
import sponsors


def test_the_contract_board_refills_to_three(new_engine):
    run = new_engine.game_world.run
    key, name = "test_hopper", "hopper"
    initial = [
        sponsors.Contract(f"h{i}", "heavy_industries", sponsors.HUNT + key, 1, reputation=3, credits=10, label=name, start_kills=0)
        for i in range(3)]
    run.contracts = list(initial)
    for contract in initial:
        run.kills[key] = run.kills.get(key, 0) + 1
        sponsors.deliver(new_engine.player, run, contract)
        assert contract.done
        assert len([c for c in run.contracts if not c.done]) == 3
