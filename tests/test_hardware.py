import unittest
from unittest import mock

from quickzap import hardware as hw_mod
from quickzap.hardware import assess, catalog, parse_meminfo, parse_nvidia_smi, parse_vm_stat, recommend


def machine(vram_gb=None, ram_total=16.0, ram_avail=10.0, unified=False):
    return {"vram_mib": int(vram_gb * 1024) if vram_gb else None, "unified": unified,
            "gpus": [{"name": "GPU de prueba", "vram_total_mib": int(vram_gb * 1024), "vendor": "nvidia"}] if vram_gb else [],
            "ram": {"total_gb": ram_total, "available_gb": ram_avail, "used_gb": ram_total - ram_avail}}


def fit(hw, family, quant="q4_K_M"):
    fam = next(f for f in hw_mod.FAMILIES if f["id"] == family)
    return assess(hw, fam["params_b"], quant)


class ParserTests(unittest.TestCase):
    def test_meminfo(self):
        r = parse_meminfo("MemTotal:       16384000 kB\nMemFree:  100 kB\nMemAvailable:    8192000 kB\n")
        self.assertEqual((r["total"], r["available"]), (16384000 * 1024, 8192000 * 1024))
        self.assertIsNone(parse_meminfo("nada"))

    def test_vm_stat(self):
        text = ("Mach Virtual Memory Statistics: (page size of 16384 bytes)\nPages free:      1000.\n"
                "Pages inactive:  2000.\nPages speculative: 500.\nPages active: 99999.\n")
        self.assertEqual(parse_vm_stat(text, 10)["available"], 3500 * 16384)

    def test_nvidia_smi(self):
        g = parse_nvidia_smi("NVIDIA GeForce RTX 3060, 12288, 1024, 551.23\nbasura\n")
        self.assertEqual(len(g), 1)
        self.assertEqual((g[0]["name"], g[0]["vram_total_mib"], g[0]["vram_used_mib"]), ("NVIDIA GeForce RTX 3060", 12288, 1024))

    def test_real_ram_and_cpu_detection_returns_data(self):
        r = hw_mod.ram()
        self.assertTrue(r["total_gb"] and r["available_gb"] is not None)
        self.assertTrue(hw_mod.cpu_info()["name"])

    def test_snapshot_has_no_personal_data(self):
        import json, getpass, platform
        blob = json.dumps(hw_mod.snapshot())
        self.assertNotIn(getpass.getuser(), blob if getpass.getuser() not in ("root", "") else "")
        self.assertNotIn(platform.node(), blob)


class RecommendationTests(unittest.TestCase):
    def test_rtx3060_8gb_16gb_ram(self):
        hw = machine(vram_gb=8)
        r = recommend(hw)
        self.assertEqual((r["model"], r["fit"]), ("qwen2.5:7b", "gpu"))
        self.assertEqual(fit(hw, "qwen2.5:7b", "q5_K_M"), "gpu")       # Q5 todavía cabe
        self.assertEqual(fit(hw, "qwen2.5:7b", "q8_0"), "hybrid")       # Q8 ya no cabe entero
        self.assertEqual(fit(hw, "qwen2.5:14b"), "hybrid")

    def test_never_recommends_a_model_that_does_not_fit_on_gpu(self):
        for vram in (2, 4, 6, 8, 12, 16, 24):
            r = recommend(machine(vram_gb=vram, ram_total=32, ram_avail=24))
            self.assertIn(r["fit"], ("gpu", "cpu"), vram)

    def test_cpu_only_gets_light_model(self):
        r = recommend(machine(ram_total=16, ram_avail=10))
        self.assertEqual((r["model"], r["fit"]), ("qwen2.5:3b", "cpu"))
        self.assertEqual(fit(machine(ram_total=16, ram_avail=10), "qwen2.5:14b"), "no")

    def test_modest_pc(self):
        r = recommend(machine(ram_total=8, ram_avail=5))
        self.assertIn(r["model"], ("qwen2.5:1.5b", "qwen2.5:3b"))
        self.assertEqual(r["fit"], "cpu")

    def test_very_low_memory_warns_instead_of_pretending(self):
        r = recommend(machine(ram_total=4, ram_avail=2))
        self.assertEqual((r["model"], r["fit"]), ("qwen2.5:0.5b", "no"))
        self.assertTrue(r["warning"])

    def test_big_gpu_gets_14b(self):
        self.assertEqual(recommend(machine(vram_gb=24, ram_total=64, ram_avail=50))["model"], "qwen2.5:14b")

    def test_apple_unified_memory(self):
        hw = machine(vram_gb=16 * 0.66, ram_total=16, ram_avail=9, unified=True)
        self.assertEqual(recommend(hw)["model"], "qwen2.5:7b")
        self.assertEqual(fit(hw, "qwen2.5:14b"), "no")

    def test_available_ram_matters(self):
        self.assertNotEqual(fit(machine(ram_total=16, ram_avail=12), "qwen2.5:7b"), "no")
        self.assertEqual(fit(machine(ram_total=16, ram_avail=3), "qwen2.5:7b"), "no")

    def test_catalog_structure_and_tags(self):
        cat = catalog(machine(vram_gb=8))
        q7 = next(f for f in cat if f["id"] == "qwen2.5:7b")
        self.assertEqual([v["name"] for v in q7["variants"]],
                         ["qwen2.5:7b", "qwen2.5:7b-instruct-q5_K_M", "qwen2.5:7b-instruct-q8_0"])
        self.assertEqual(q7["variants"][0]["size_gb"], 4.7)   # coincide con el tamaño publicado en Ollama
        self.assertTrue(all(v["fit"] in hw_mod.FIT_LABELS for f in cat for v in f["variants"]))

    def test_light_models_available_for_modest_pcs(self):
        sizes = {f["id"]: f["params_b"] for f in hw_mod.FAMILIES}
        self.assertLessEqual(sizes["qwen2.5:0.5b"], 0.5)
        self.assertTrue(any(p <= 1.6 for p in sizes.values()))


if __name__ == "__main__":
    unittest.main()
