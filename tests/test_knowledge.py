from __future__ import annotations

from avalon.enums import RoleType
from avalon.knowledge import KnowledgePacket, compute_setup_knowledge
from avalon.players import Player


def _make_player(identifier: str, name: str, role: RoleType) -> Player:
    return Player(player_id=identifier, display_name=name, role=role)


def test_merlin_vision_excludes_mordred() -> None:
    players = [
        _make_player("p1", "Merlin", RoleType.MERLIN),
        _make_player("p2", "Assassin", RoleType.ASSASSIN),
        _make_player("p3", "Morgana", RoleType.MORGANA),
        _make_player("p4", "Mordred", RoleType.MORDRED),
        _make_player("p5", "Percival", RoleType.PERCIVAL),
        _make_player("p6", "Arthur", RoleType.LOYAL_SERVANT),
    ]

    packets = compute_setup_knowledge(players)
    merlin_packet = packets["p1"]
    assert isinstance(merlin_packet, KnowledgePacket)
    assert "p2" in merlin_packet.visible_player_ids
    assert "p3" in merlin_packet.visible_player_ids
    assert "p4" not in merlin_packet.visible_player_ids


def test_percival_receives_ambiguous_group() -> None:
    players = [
        _make_player("p1", "Merlin", RoleType.MERLIN),
        _make_player("p2", "Percival", RoleType.PERCIVAL),
        _make_player("p3", "Morgana", RoleType.MORGANA),
        _make_player("p4", "Assassin", RoleType.ASSASSIN),
        _make_player("p5", "Galahad", RoleType.LOYAL_SERVANT),
    ]

    packets = compute_setup_knowledge(players)
    percival_packet = packets["p2"]
    assert percival_packet.ambiguous_player_id_groups
    ambiguous_group = percival_packet.ambiguous_player_id_groups[0]
    assert set(ambiguous_group) == {"p1", "p3"}


def test_oberon_hidden_from_other_minions() -> None:
    players = [
        _make_player("p1", "Merlin", RoleType.MERLIN),
        _make_player("p2", "Assassin", RoleType.ASSASSIN),
        _make_player("p3", "Morgana", RoleType.MORGANA),
        _make_player("p4", "Oberon", RoleType.OBERON),
        _make_player("p5", "Minion", RoleType.MINION_OF_MORDRED),
    ]

    packets = compute_setup_knowledge(players)
    assassin_packet = packets["p2"]
    minion_packet = packets["p5"]
    oberon_packet = packets["p4"]

    # Assassin and generic minion should see each other but not Oberon.
    assert set(assassin_packet.visible_player_ids) == {"p3", "p5"}
    assert set(minion_packet.visible_player_ids) == {"p2", "p3"}

    # Oberon remains isolated from the rest of the evil team.
    assert not oberon_packet.has_information
