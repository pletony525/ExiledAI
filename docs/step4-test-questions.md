# Step 4 Test Questions — RAG Loop Go/No-Go Gate

Per [[POE2 Advisor — v1 Build Plan]] Step 4: "test manually against real build/trading questions... this is the actual go/no-go gate." These questions are grounded in patterns real players actually ask (per web research on PoE2 community discussions), not invented ones — categorized by what our scraped corpus (uniques, skill gems, support gems, mods) can and can't actually answer.

Run each through the CLI script once it's built. For each, check the note under it — not a strict pass/fail, but "did retrieval surface the right chunks, and did the answer honestly reflect what's there."

## Direct lookups (should nail these — easiest case)

1. **"What does the unique item Ab Aeterno do?"**
   Expect: the exact explicitMods (movement speed, armour/evasion/ES increase, dodge roll avoids hits) pulled up as the top match.

2. **"What does the skill gem Boneshatter do?"**
   Expect: Boneshatter's tags/description/mods surfaced directly.

3. **"What level do I need to use Abyssal Pact?"**
   Expect: the requirements line (Level range, Int requirement) from that gem's chunk.

## Cross-referencing (harder — real test of retrieval, not just keyword match)

4. **"What are some good support gems for a minion build?"**
   Expect: support gems tagged/described around minions surfacing near the top. This requires the embedding to connect "minion build" to gems whose text mentions Minion tags/effects — a real test of semantic (not just keyword) retrieval.

5. **"What unique gloves are good for a spell damage build?"**
   Expect: unique items in the Gloves category whose explicitMods mention spell damage, cast speed, or caster stats. Tests whether retrieval can filter by both item slot and build intent simultaneously.

6. **"What mods can roll on a ring?"**
   Expect: mod chunks whose `spawn_no`/`Can roll on` metadata includes "ring" — this should retrieve cleanly since it's a direct metadata match, but the answer needs to synthesize across several distinct mod chunks, not just quote one.

7. **"What's a good affix to look for on boots for resistances?"**
   Expect: resistance-related mods from the Boots_str/dex/int category chunks surfacing near the top.

## Precision/tier checks (numeric correctness matters)

8. **"What's the minimum item level for the 'of the Brute' suffix?"**
   Expect: exact `Minimum item level` value from that mod's chunk (this is a case where I already saw the real data — should be level 1).

9. **"How much armour does Ab Aeterno have?"**
   Expect: exact number (296) from the properties field, not a paraphrase or made-up figure — a good hallucination check on numeric facts.

## Out-of-scope traps (the corpus should NOT have this — tests honesty over confidence)

10. **"What's the best beginner class in POE2?"**
    Not in the corpus at all (no strategy/meta-guide content was scraped, only item/gem/mod data). A good system should say it doesn't have this information rather than inventing a plausible-sounding answer.

11. **"How much does a Headhunter cost right now?"**
    Live trade pricing is explicitly out of v1 scope per the build plan (deferred stretch goal — "prices too volatile to embed"). Should decline/flag as unavailable, not fabricate a price.

12. **"Should I follow a build guide or figure it out myself?"**
    General meta-strategy opinion question, not present in scraped data. Tests the same honesty behavior as #10 from a different angle (opinion vs. fact).

## What a "good enough to proceed" result looks like

- Questions 1-3 (direct lookups) should work well immediately — if these fail, something is broken in basic retrieval, not just tuning.
- Questions 4-7 (cross-referencing) are the real signal for whether per-entry chunking (the Step 3 assumption) is sufficient, or whether chunking/retrieval needs revisiting.
- Questions 8-9 (precision) catch hallucination on numbers, which matters a lot for a build advisor — wrong numbers are worse than no answer.
- Questions 10-12 (out-of-scope) are a pass/fail on honesty: confidently making things up here is a red flag regardless of how well 1-9 go.

## Related

- [[POE2 Advisor — v1 Build Plan]]
