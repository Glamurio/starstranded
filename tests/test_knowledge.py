from capabilities import CapabilitySet, grants
from knowledge import Fact, Know, Knowledge, format_fact, reveal_level
from skills import Skill, SkillSet, skills

NOBODY = SkillSet()
NONE = CapabilitySet()


def test_skillset_clamps_and_combines():
    s = skills(biology=9, survival=-3)
    assert s.level(Skill.BIOLOGY) == 5 and s.level(Skill.SURVIVAL) == 0
    assert skills(biology=2).combine(skills(biology=2, chemistry=1)).level(Skill.BIOLOGY) == 4
    assert s.level(Skill.GEOLOGY) == 0


def test_scanner_alone_reads_trivial_and_hints_next_tier():
    easy = Fact("name", Skill.BIOLOGY, 1, "Rabbit")
    mid = Fact("diet", Skill.BIOLOGY, 2, "herbivore")
    hard = Fact("uses", Skill.BIOLOGY, 3, "fur burns well")
    assert reveal_level(easy, NOBODY, NONE) is Know.FULL
    assert reveal_level(mid, NOBODY, NONE) is Know.PARTIAL
    assert reveal_level(hard, NOBODY, NONE) is Know.UNKNOWN


def test_expertise_unlocks_domain_facts_but_not_others():
    uses = Fact("uses", Skill.BIOLOGY, 4, "fur burns well")
    toxin = Fact("toxicity", Skill.CHEMISTRY, 4, "toxic")
    biologist = skills(biology=3)
    assert reveal_level(uses, biologist, NONE) is Know.FULL
    assert reveal_level(toxin, biologist, NONE) is Know.UNKNOWN
    assert reveal_level(uses, NOBODY, NONE) is Know.UNKNOWN


def test_capability_tag_gives_a_bonus_for_matching_facts():
    fact = Fact("diet", Skill.BIOLOGY, 3, "x", capability="species_identification")
    assert reveal_level(fact, skills(biology=1), NONE) is Know.PARTIAL
    assert reveal_level(fact, skills(biology=1), CapabilitySet(grants("species_identification"))) is Know.FULL


def test_knowledge_only_improves_and_persists():
    k = Knowledge()
    fact = Fact("hardness", Skill.GEOLOGY, 2, 7.2)
    assert k.scan("material:flint", [fact], NOBODY, NONE)  # PARTIAL learned
    assert k.level("material:flint", "hardness") is Know.PARTIAL
    assert k.scan("material:flint", [fact], NOBODY, NONE) == []  # nothing new
    assert k.scan("material:flint", [fact], skills(geology=1), NONE)  # upgraded
    assert k.level("material:flint", "hardness") is Know.FULL
    assert not k.learn("material:flint", "hardness", Know.PARTIAL)  # never downgraded
    assert Knowledge.from_dict(k.to_dict()).level("material:flint", "hardness") is Know.FULL


def test_formatting_hides_and_buckets():
    fact = Fact("hardness", Skill.GEOLOGY, 2, 7.2)
    assert format_fact(fact, Know.UNKNOWN) is None
    assert format_fact(fact, Know.PARTIAL) == "high?"
    assert format_fact(fact, Know.FULL) == "7.2"
    assert format_fact(Fact("diet", Skill.BIOLOGY, 2, "herbivore", hint="eats something"), Know.PARTIAL) == "eats something"
