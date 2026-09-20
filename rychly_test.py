"""
Rychlý test generátoru - vygeneruje jen 10 postupů pro rychlé ověření kvality.
Spusť: python rychly_test.py
"""
import runpy
import config

# Dočasně snížíme požadavky pro rychlý test (nemodifikuje config.py na disku)
config.MAX_VYSLEDNYCH_POSTUPU = 10
config.HUSTOTA_KANDIDATU_KM2 = 2.0  # ~100 kandidátů pro 49km2 mapu

print("="*60)
print("🚀 RYCHLÝ TEST – generuji 10 postupů pro ověření kvality")
print("   (Pro plnou sadu 500 postupů spusť: python 9_generator_postupu.py)")
print("="*60)

runpy.run_path("9_generator_postupu.py", run_name="__main__")
