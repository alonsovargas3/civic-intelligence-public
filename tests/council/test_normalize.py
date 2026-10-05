from atx_council.normalize import normalize_member_name, same_member


def test_contribution_recipient_format():
    assert normalize_member_name("Adler, Stephen") == ("adler", "stephen")
    assert normalize_member_name("Alter, Alison B.") == ("alter", "alison")
    assert normalize_member_name('Casar, Gregorio E. "Greg"') == ("casar", "gregorio")


def test_sponsor_title_format():
    assert normalize_member_name("Council Member Ryan Alter") == ("alter", "ryan")
    assert normalize_member_name("Mayor Steve Adler") == ("adler", "steve")
    # accents are folded so cross-source names match
    assert normalize_member_name("Mayor Pro Tem José ''Chito'' Vela") == ("vela", "jose")


def test_accent_folding_bridges_sources():
    # contribution "Velasquez, Jose" (no accent) must match sponsor "José Velásquez"
    assert normalize_member_name("Velasquez, Jose") == ("velasquez", "jose")
    assert normalize_member_name("Council Member José Velásquez") == ("velasquez", "jose")
    assert same_member(normalize_member_name("Velasquez, Jose"),
                       normalize_member_name("Council Member José Velásquez")) is True


def test_non_member_or_blank():
    assert normalize_member_name("") is None
    assert normalize_member_name(None) is None
    # a PAC / org (no comma, no person title) -> not a member name
    assert normalize_member_name("Austin Fire Fighters PAC") is None


def test_same_member_matches_nickname_and_short_forms():
    # Steve/Stephen and Greg/Gregorio match on last + first-prefix
    assert same_member(("adler", "stephen"), ("adler", "steve")) is True
    assert same_member(("casar", "gregorio"), ("casar", "greg")) is True
    assert same_member(("alter", "alison"), ("alter", "alison")) is True


def test_same_member_keeps_distinct_people_apart():
    # two different Alters must NOT match (Alison vs Ryan)
    assert same_member(("alter", "alison"), ("alter", "ryan")) is False
    # different last names never match
    assert same_member(("adler", "steve"), ("alter", "steve")) is False
