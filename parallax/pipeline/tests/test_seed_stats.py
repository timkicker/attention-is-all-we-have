from pipeline.seed_stats import app_values


def test_embed_rate_gets_per_s_and_gpu_for_the_hood_grid():
    out = app_values(
        {"laptop_ollama": 19.98, "verda_a100": 4555.2},
        {"gpu": "NVIDIA A100-SXM4-80GB"},
        {"revisions": 862076},
        (1118463, 532372, 292344),
    )
    assert out["embed_rate"]["per_s"] == 4555.2 and "A100" in out["embed_rate"]["gpu"]
    assert out["embed_rate"]["laptop_ollama"] == 19.98  # docs keep reading the per-machine keys
    assert out["fi_revisions"] == 862076 and out["fi_lives"] == 1118463 and out["fi_dead_1y"] == 292344


def test_without_verda_or_m_lives():
    out = app_values({"laptop_ollama": 19.98}, None, None, (0, 0, 0))
    assert out == {"embed_rate": {"laptop_ollama": 19.98, "per_s": 19.98, "gpu": None}}
