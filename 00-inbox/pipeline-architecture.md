# Deal Analysis Pipeline — Business Logic Reference

Full pipeline from pitch-deck upload through the final Investment Committee (L1) memo, how Gemini and the web-research providers are actually used under the hood, the operator-facing dashboard built on top of it, the Elixir↔Trigger.dev integration layer, the interactive knowledge-agent chat feature, and a note on what's provisioned-but-dormant vs. explicitly out of scope — audited against the current codebase to close gaps, not just narrated from memory.

Stack: Elixir/Phoenix (`lib/deals_analysis`) for state, storage orchestration, and UI; Trigger.dev TypeScript workers (`src/trigger`) for the document/LLM pipeline; Gemini (`@google/genai`, native structured JSON output) as the primary extraction/synthesis model; Jina and Exa as web deep-research providers; Tigris (S3-compatible) for object storage.

---

## Core Decision Logic — Every Rule That Classifies, Flags, or Scores a Fund

This is the part of the pipeline that actually matters most: the specific rules that decide what a document *is*, what a fund *is*, what gets *flagged*, and what a fund *scores*. Everything else in this doc (storage, orchestration, providers) exists to feed evidence into these decisions. Consolidated here as one reference; full detail and code pointers are in the linked section.

**1. What is this document, and does it even get analyzed?** (§1-2)
One LLM call classifies every uploaded file into one of 12 `document_type` values. Only 8 of them — `pitch_deck, tear_sheet, fact_sheet, fund_overview, investor_presentation, ppm, marketing_flyer, quarterly_report` — pass the promotion gate and trigger analysis at all. The other 4 (`data_room_document, financial_statement, legal_document, unknown`) are stored and never analyzed. **This single gate determines whether a fund gets evaluated at all.**

**2. What kind of fund is this?** (§3)
One dedicated LLM pass, run before any other extraction, decides three things that gate every later stage: `primaryAssetClass` (PE / Hedge Fund / VC / Real Estate / Private Credit / Fund of Funds / Infrastructure), `isOpenEnded` (structure), and `managerClassification` (Emerging / Transitioning / Established). This decision selects which extraction schemas run, which scoring rubric applies, and which research mission pack fires. **Get this wrong and every downstream judgment is scored against the wrong yardstick.**

**3. Does the deck's story match the official record?** (§5)
Deterministic (non-LLM) comparison logic flags mismatches between what the deck claims and what regulatory filings show:
- Website / HQ location mismatch → flagged
- AUM outside a `0.4×–2.5×` tolerance band of the filed figure → flagged as `magnitude_mismatch`
- Deck claims the manager runs private funds but the filing shows none → flagged `inconsistent`, called out in code as a **"major red flag"**
- Filed disciplinary history (Item 11: criminal/regulatory/civil) → surfaced as a boolean + categorized breakdown, the single highest-signal red flag in the entire pipeline

**4. How much scrutiny does each person get?** (§6)
Every named team member is classified into one of 7 tiers (`key_principal` down to `misc`), which mechanically determines research depth (3 to 10 research tasks run per person). The classification is fail-open by design: unclear context defaults to `extended_team`; a parse failure defaults to `key_principal` — biased toward *not* under-scrutinizing someone important.

**5. What's missing or suspicious in the research?** (§8)
An automated "skeptic" pass (`critical-audit-gap-analysis.ts`) re-reads every fund's consolidated research and checks five specific failure modes — Performance Blind Spots, Structural Omissions, Operational Risk, Regulatory/Compliance Nuance, Data Staleness — and outputs `redFlagsDetected[]`, `caseNumbers[]`, `tier2ServiceProviders[]`, `missingDataForWebSearch[]`. These fields **mechanically trigger a second round of targeted research** (not just a note in a report). A stricter "Emerging Manager Protocol" activates automatically when the fund is a first-time/early manager.

**6. What's the actual score?** (§9) — the core of the platform
- Every fund is scored on ~20 criteria across 4 categories (A: Operational Quality, B: Sourcing & Value Creation, C: Capital & Risk Mechanics, D: Operations & Compliance), with **the specific criteria set varying by asset class** (a rubric matrix, not one fixed checklist).
- Every criterion lands on a fixed 5-tier scale: `Exemplary → Strong → Adequate → Weak → Unacceptable`. No numeric weights, no combined score.
- **`Unacceptable` frequently doubles as an automatic VETO** — specific conditions (e.g. no key-person clause, no management-fee offset, fraudulent service providers) are written directly into the rubric text as instant-fail conditions, regardless of how strong anything else is.
- For Real Estate PE specifically, a separate quantitative table (`repe-breaking-points.json`, refreshed from external market data) gives hard min/max cutoffs (DSCR, LTV, net IRR, cash-on-cash) checked against the deal's own underwriting numbers — a second, numeric-only gate layered on top of the qualitative rubric.
- Every score is produced by two independent LLM passes (one lenient, one mechanically strict) reconciled by a third synthesis pass — specifically so a single lenient read can't produce an inflated rating.

**7. What does the Investment Committee actually see as the verdict?** (§10)
- **Verdict**: `ADVANCE / DECLINE / CONDITIONAL` — the single top-line decision, plus `what_would_change_our_mind[]`.
- **Claims Ledger**: every checkable claim from the deck is marked `CONFIRMED / CONTRADICTED / UNVERIFIABLE` against outside evidence — this is where deck oversell gets caught explicitly (e.g. a founder claiming credit for 11 deals when the record supports 5).
- **Flags**: every issue is severity-ranked `CRITICAL / WARNING / INFO`, each paired with the exact question to ask the manager.
- All of this is generated by feeding the already-computed scoring (#6) and gap-analysis (#5) results directly into the memo-writing prompt — the verdict is built *on top of* those upstream judgments, not derived independently of them, so a fund can't get a clean verdict that contradicts its own scorecard.

---

## 1. Document Upload & Ingestion

**Entry points.** Two paths: (1) webhook upload (`FundUploadController.upload/2`) — an external system posts `{file_urls, file_names, callback_url, workspace_id, deal_id}`, server pulls each URL; (2) direct browser upload via LiveView.

**Storage & dedup.** Files land in Tigris at key `decks/<sha256>.<ext>` — content hash is the storage key, so identical bytes never duplicate. SHA-256 computed over raw bytes doubles as DB lookup key (`get_client_upload_by_sha/1`). MIME type inferred from extension (pdf/pptx/ppt/xlsx/docx recognized explicitly; else `application/octet-stream`, not rejected).

**Data model.** `Uploads.ClientUpload` is a state-machine resource: `uploading → pending_initialization → processing → downloading → generating_thumbnails → uploading_to_gemini → processing_gemini → classifying → analyzing → promoted/completed/failed`. Key fields: `sha`, `file_key`, `run_id`, `analysis_result` (holds webhook metadata transiently), `gemini_file_id/uri`.

**Promotion rule (the core gate).** After classification (§2), only documents whose `document_type` is in a hardcoded marketing-document allowlist — `pitch_deck, tear_sheet, fact_sheet, fund_overview, investor_presentation, ppm, marketing_flyer, quarterly_report` — get "promoted": a `Fund` record is created/matched by extracted `fund_name`, a `Document` record is created, and the full downstream pipeline (`workflow-master-fund`) auto-triggers. Everything else (`data_room_document`, `financial_statement`, `legal_document`, `unknown`) is stored but never enters analysis.

**Reliability.** A polling sweep (`sweep_processing_uploads/0`) reconciles stuck uploads against Trigger.dev run status. Uploads/batches are cancellable, which also cancels downstream Trigger.dev runs.

---

## 2. Page Conversion & Document Classification

**Classification.** `workflow-document-classify-and-summary`: PDF → Gemini Files API upload → one structured-output LLM call (Gemini Flash-Lite) returning enum-constrained `document_type` (the 12 values above plus `unknown`), `fund_name` (must be the actively-raised fund, not a past vintage), `company_name`, `key_principals[]`, `summary`, `fund_classification`, `asset_class`, `sector`. This call also opens a per-fund Gemini File Search store (RAG index) used by every later stage.

**Page rasterization — full mechanics.** Two implementations run this, effectively in parallel with classification:
- `pdf_to_images` (`src/trigger/pitch-deck/pdf-to-images.ts`) — concurrency 1, `large-2x` machine, 10-min max, produces `preview` (144 PPI) and `thumbnail` (36 PPI) sizes.
- `workflow-generate-thumbnails` (`src/trigger/pitch-deck/generate-thumbnails.ts`) — same limits, adds a `large` (300 PPI) tier, and parallelizes rasterization across CPU-core-derived chunks so a 60-page deck doesn't render serially.

Both start with `pdfinfo` to get the page count, then rasterize with `pdftoppm`; if `pdftoppm` fails on a given page (corrupt embedded fonts, unusual color profiles), the code falls back to ImageMagick (`magick`) rather than failing the whole document. Every image is written to Tigris at key `<sha>/<paddedPage>/<sizeLabel>.jpg` — the same content-hash-based key scheme as the source file, so re-processing the same deck never re-renders or duplicates images.

**Two-phase priority rendering.** `regenerate_pdf_preview/1` (`lib/deals_analysis/documents/workflows.ex`) doesn't request the whole deck at once. It fires two separate Trigger.dev requests: page-1 thumbnail at priority 10 (so the fund's card/list-view entry has a preview image within seconds of upload), then the full deck at priority 0 (so it doesn't block the fast path but still completes before extraction needs the images). This is why a newly uploaded deck shows a cover-page thumbnail almost immediately while the rest of the pages are still rendering in the background.

**Orchestration — what fires on every single upload.** The moment a document is promoted (§1's allowlist gate), one task kicks off the entire rest of the pipeline: `workflow-master-fund` (`master-workflow.ts`, up to 4h max duration, retry 1-2x on failure). This is the one workflow that runs, unconditionally, every time a new marketing document clears the promotion gate — nothing downstream (extraction, diligence, research, scoring, memo) is triggered any other way. Its sequence, each step wrapped in its own try/catch so one failure nulls that result without aborting the run:
1. `processPitchDeckWorkflow` — schema/entity extraction (§3-4), SEC-entity resolution (§5, run once here so later diligence steps can skip it), fund-maturity classification
2. Person research per key principal, batch-triggered via `personResearchWorkflow` (§6-7) — skipped entirely if no principals were found in step 1
3. `fundDeepDiligenceWorkflow` (§8) — explicitly skips re-running SEC diligence, since step 1 already produced it
4. `fullScoringWorkflow` (§9)
5. `l1AnalysisWorkflow` (§10) — final IC memo

Steps 2 and 3 both only depend on step 1's output, but as currently written they run **sequentially, not concurrently** — `master-workflow.ts` awaits step 2 (person research) fully before starting step 3 (fund deep diligence). This is a real optimization opportunity, not yet taken: person research and fund research have no dependency on each other and could run in parallel. Note also that step 1 is the one step *not* wrapped in try/catch — a failure there aborts the entire run, unlike steps 2-5 which fail gracefully.

**Re-upload / re-processing behavior.** Because promotion is keyed off the extracted `fund_name` and the file's own content hash, re-uploading the exact same deck bytes is caught by the SHA-256 dedup check in §1 and never re-triggers `workflow-master-fund` at all. Uploading a *new* file for a fund that already exists (e.g. an updated quarterly deck) creates a new `Document` record linked to the existing `Fund`, and does trigger a fresh `workflow-master-fund` run scoped to that new document — the fund-level entity persists and accumulates documents/analyses over time rather than being recreated per upload.

**Completion sync.** When all five steps resolve (or fail gracefully), `workflow-master-fund` posts a webhook back to the Elixir app at `{APP_URL}/api/webhooks/trigger_sync` with `_sync: {state: "analysis completed", l1_analysis_cache, parsed_data_merge}`, which is what flips the `Document` state machine to `scoring completed` and makes the finished analysis visible in the UI. If the original upload came in via the webhook path (§1), the stored `callback_url` also receives a completion notification at this point.

**Queues.** Named Trigger.dev queues with env-tunable concurrency, so a burst of uploads doesn't starve any one stage of capacity: `diligence-workflows`, `llm-generation` (default 20), `sec-scraping` (default 10), `jina-deep-research`, `jina-api`, `deep-research-bulk` (default 10), `test-generation` (fixed 1).

---

## 3. Fund Classification

**Where it happens.** A mandatory "Pass 1" extraction using only the `fund_overview_and_terms` schema, run before any other extraction (Gemini 3.5 Flash, high thinking level, over the full PDF via Gemini file API — not the RAG store).

**Decision fields (embedded in the schema, forced chain-of-thought):**
- `primaryAssetClass`: enum `Private Equity, Hedge Fund, Venture Capital, Real Estate, Private Credit, Fund of Funds, Infrastructure, Unknown`
- `hedgeFundStrategy` (if applicable)
- `isOpenEnded` — open-ended/evergreen vs. closed-end draw-down
- `classificationReasoning` — forced free-text justification
- `managerClassification`: enum `Emerging, Transitioning, Established` (+ own reasoning field)

**What it gates.** Normalized `primaryAssetClass` determines which asset-class-specific extraction schemas run downstream (`hedge_fund_metrics`, `venture_capital_metrics`, `real_estate_metrics`, `private_credit_metrics`, `private_equity_metrics` — each fires only for its matching class), which asset-class-specific scoring rubrics apply (§8), and which fund-research "mission" pack runs (§7).

**Taxonomy fragmentation.** Three overlapping taxonomies exist: the extraction-schema enum above; a richer `capital_structure × asset_class × sub_asset_class` taxonomy in `schemas/common/taxonomy.ts` (e.g. Real Estate has 22 sub-classes); and a third, separate `asset_class.schema.json` with snake_case values and a `primary_strategy` enum (`pe_leveraged_buyout`, `vc_early_stage`, `credit_direct_lending`, etc.) plus `fund_structure` (direct/fund-of-funds/secondary/co-investment) and `is_esg_impact`. These represent different eras of the same concept, not reconciled.

---

## 4. Data Extraction from Pitch Decks

**Pipeline.** Classification → parallel per-schema extraction → master-schema mapping → graph artifact generation → L1 analysis.

**Two-step extraction pattern (every schema, not just classification):**
1. Generate a comprehensive markdown report from the raw PDF, forcing verbatim quoting with page citations (`[Page X]`)
2. Second LLM call over that markdown with `responseSchema` (Zod → JSON Schema) in Gemini's native structured-output mode — this avoids the model inventing numbers directly in JSON mode

**Core schemas (every asset class):**
- `fund_overview_and_terms` — legal names, vintage, target size/hard cap, management fee, carry, hurdle, GP commitment, fund life, minimum LP commitment, catch-up, fee step-downs, sub/redemption/lock-up terms, domicile, regulatory exemptions (Rule 506(b)/(c), 3(c)(1)/3(c)(7)), service providers, risk disclosures
- `strategy_and_portfolio` — thesis, construction rules
- `team_and_track_record` — key principals (with investment-team/IC flags, bios, prior firms), firm leadership, advisors, aggregate IRR/MOIC/DPI/RVPI, prior vehicles (per-vintage size/deal count/gross-net IRR-MOIC), case studies (entry/exit valuation, MOIC, holding period)
- `warehoused_deals` — seeded/pipeline deals

**Asset-class-specific schemas** gated by §3's classification: `hedge_fund_metrics`, `venture_capital_metrics`, `real_estate_metrics`, `private_credit_metrics`, `private_equity_metrics`.

**Numeric normalization.** Every monetary/percentage/duration/multiplier field captures a verbatim `source_number_text` first, then a *separate*, smaller LLM call parses it into structured `{amount, magnitude: ONES|HUNDREDS|THOUSANDS|MILLIONS|BILLIONS|TRILLIONS}` or a range — this two-tier extract-then-normalize avoids hallucinated arithmetic.

**Consolidation.** Each schema group extracted independently in parallel (one Gemini call per schema over the full document, concurrency 10), merged by schema name into `consolidatedKnowledge` — topic-level merging, not page-by-page reconciliation. A separate/older path (`consolidate-entities-partitioned.ts`) does true per-slide fan-out across 6 fixed partitions (summary/company/financials/market/people/investment) — appears to be a legacy strategy predating the schema-per-domain approach.

**Downstream.** `master-schema-mapper.ts` coerces the consolidated knowledge into a `master_data` object stored on the Elixir `Fund` resource; a separate LLM call converts it into Cypher `MERGE` statements for a graph DB (Fund/Manager/Person/Company/Strategy/Location nodes).

---

## 5. SEC Filing Diligence

**Workflow (acquire → identify → extract → verify), `acquire-sec-diligence.ts`:**
1. **Entity categorization** (LLM-classified, Jina web-search fallback): `registered` (mutual fund/ETF) / `private` (hedge fund/PE/VC/RIA) / `public_manager`. Category determines target document set — private funds get ADV Part 1, ADV Part 2 Brochure, Form D, Form 13F, Schedule 13D/13G; registered funds get Prospectus/SAI/N-CSR/N-PORT; public managers get private-fund docs plus 10-K/10-Q.
2. **Acquisition** — `SECProvider` hits SEC EDGAR's public submissions API (`data.sec.gov/submissions/CIK{cik}.json`, 24h cache) and unwraps SGML/XML/PDF filing envelopes.
3. **Identification** — deterministic pattern matching, not an LLM: XML tag inspection for Form D/13F/Forms 3-4-5/Schedule 13D-13G; for PDFs, `pdftotext -layout` + regex/keyword rules (e.g. "uniform application for investment adviser registration" ⇒ ADV Part 1) returning `confidence: high|medium|low` and an `isMerged` flag for combined Part 1+2 PDFs.
4. **Extraction** — type-specific extractors run concurrently (concurrency 5): Form D/13F/ownership XML, ADV Part 1 (hybrid regex + LLM — deterministic regex for Item 1 identity/Item 5 AUM because it's fast and hallucination-free; Gemini for multi-page tabular sections like Schedule A/R and Item 11 disciplinary tables because layout drift breaks regex), ADV Part 2 brochures (LLM narrative summarization per item).

**Concrete ADV fields extracted:**
- **Identity**: legal name, registration/CRD number, file number, Chief Compliance Officer, website
- **AUM/scale**: total regulatory AUM, total accounts, asset-class breakdown percentages (12 standard SEC asset classes), custodians, employee counts
- **Conflicts/custody**: proprietary trading, principal transactions, soft-dollar arrangements, placement-agent compensation, custody status, annual surprise exam
- **Ownership** (Schedule A): direct owners/executives with title, ownership-percentage band (NA<5% / A 5-10% / B 10-25% / C 25-50% / D 50-75% / E>75%), control-person flag, entity-vs-individual flag
- **Schedule R**: relying advisers' names + CRD numbers (umbrella registration)
- **Per-fund reporting** (Section 7.B.1): GAV, master/feeder structure, jurisdiction, fund type, minimum investment, Form D file numbers, % owned by related persons/fund-of-funds/non-US persons, auditor + opinion type, prime brokers, custodians, administrator, marketers
- **Disciplinary history** (Item 11): boolean `has_any_flags` + categorized breakdown (criminal 11.A/B, regulatory 11.C-G, civil 11.H) + free-text `disciplinary_summary`
- **ADV Part 2A Brochure** (narrative, LLM-summarized per item): advisory business/services, fee schedule, performance fees/side-by-side management, client types/minimums, strategies/risk, disciplinary information, other financial affiliations, code of ethics/conflicts, brokerage practices/soft dollars, referral payments, custody, investment discretion

**Entity match-verification (`match-verification.ts`)** — deterministic, cross-checking pitch-deck claims against the SEC record:
- Domain match: exact / mismatch / missing (URL normalized — strip protocol/www/trailing slash, lowercase)
- Location match: exact_city_state / state_only / mismatch
- AUM match: parses free-text AUM into numeric magnitude, checks against an asymmetric tolerance band — `lowerBound = dbVal * 0.4`, `upperBound = dbVal * 2.5` (decks round up, filings can under-report) — returns magnitude_match/mismatch/unparseable/missing
- Fund-flag match: if deck claims private funds exist but SEC's `has_private_funds` is `false`, flags `inconsistent` (called out as a "major red flag" in code comments)

No single numeric confidence score — a struct of four categorical match results (`MatchChecks`) is handed upstream for a judge/LLM to weigh.

**Other public-data sources queried:**
- **SEC Form D** (DuckDB/Parquet over EDGAR bulk TSVs) — ground-truth registry of private placement/exempt offerings; CIK/entity name/related persons lookup
- **Form 13F** — quarterly institutional public-equity holdings; position sizing for large managers
- **Schedule 13D/13G** — >5% beneficial ownership disclosures; activist vs. passive stakes
- **Forms 3/4/5** — insider ownership-change filings
- **DOL Form 5500** — ERISA pension-plan annual filings; extracts `sponsor_ein, sponsor_name, plan_name, invested_fund, investment_size` for LP-side pension investor discovery
- **IRS Form 990 / TEOS** — nonprofit/foundation/endowment tax returns; extracts `investor_ein, investor_name, invested_fund, investment_size` for foundation/endowment LP discovery. The Trigger.dev tasks (`form990-ingestion.ts`, `sync-form990-teos.ts`, `teos-worker.ts`, `search-form990-db.ts`) are the query/sync layer; the actual heavy lifting — parsing raw IRS XML — happens Elixir-side in `DealsAnalysis.Teos.Extractor.extract_xml/1` (`lib/deals_analysis/teos/extractor.ex`), a regex-based Form 990/990-PF parser with entity-dedup logic over related-org/investment groups (merges by name, keeps max asset amount seen, filters placeholder rows like "SEE SCHED"). Invoked via `mix extract.irs_990`, a manually-run, OTP-concurrent bulk job (not scheduled) sized for a dedicated high-core machine — it processes ~2M IRS XML files, fanning work across `2× CPU core count` workers, and produces a fund-name-normalization view (`extracted_funds`, stripping LLC/INC/CORP/LP/FUND suffixes) that entity-matching elsewhere in the pipeline relies on.
- **ACFR** (Annual Comprehensive Financial Reports) — state/municipal/public-pension audited financials; `government_name`/`invested_fund` pairs for public-pension LP discovery

All three (5500/990/ACFR) normalize into DuckDB/Parquet search indexes with corporate suffixes stripped (LLC/LP/CAPITAL/PARTNERS) for fuzzy ILIKE matching. `analyze-firm-investors.ts` chains Form D (fund names for a firm) → Form 990 search (nonprofit LPs in each fund) to build an LP roster for a manager.

---

## 6. Key Personnel Intelligence

**Trigger.** A fund's team roster (pitch-deck extraction + website scraping + filings) is verified/classified per person by `verify-key-principals.ts`.

**7-way role taxonomy (Gemini Flash-Lite, strict JSON schema, per person):**
1. `key_principal` — the 1-2 top-level, day-to-day heads of *this specific fund* (excludes parent-company CEOs/Chairmen)
2. `fund_principal` — senior investment pros dedicated to the fund but not lead decision-makers
3. `firm_leadership` — parent-firm executives or partners from unrelated strategies
4. `advisor` — formal advisors without daily deployment authority
5. `former_member` — departed people (guarded against false positives from bios listing prior employers)
6. `extended_team` — VPs/Associates/Analysts
7. `misc` — admin/operational staff

Fail-open design: no research context → defaults to `extended_team`; parse failure/exception → defaults to `key_principal` (biased toward inclusion rather than silently dropping someone important). Output is seven buckets, each entry carrying `classificationReasoning` and a possibly `corrected_title`.

**Underlying research taxonomy** (`research_task_definitions/person/*.toml`, all Jina-driven, 1M token budget, high reasoning) — 10 categories, each with its own exclusion rules to avoid overlap:
- **preliminary-search** — broad initial sweep, feeds all downstream tasks as disambiguation context
- **generic** — bio/education/speaking/publications not tied to employment
- **employment-history** — chronological employer/title/dates/responsibilities, excludes board/advisory roles
- **regulatory-compliance** — routine compliance footprint (Form ADV 2B, Form BD, U4/U5, FATCA/CRS officer roles), distinct from forensic (no allegations/penalties)
- **reputation** — third-party media quotes, awards, spin-outs, LP sentiment, excludes firm-authored marketing
- **credentials** — degrees, Tier-1 certifications (CFA/CAIA/CPA), bar admissions, FINRA/FCA licenses
- **governance** — board/LPAC seats, voting vs. observer distinction
- **performance** — IRR/MOIC/TVPI/DPI plus deal/exit evidence and attribution (Lead/Co-Lead/Sourced)
- **forensic-regulatory** — SEC/FINRA/CFTC/FCA enforcement, Wells notices, bankruptcies, fiduciary-breach litigation
- **oba-conflicts** — outside business activities, family-office ties, personal GP stakes, side letters

`templates.toml` holds Mustache snippets injecting upstream outputs into downstream prompts. All prompts share an "extract, don't score" directive — judgment is deferred to the verify-key-principals classification step and consolidation.

**Tiered execution** (`workflow.json`) — a dependency graph drives three depth tiers: `firm_leader` (10 tasks, includes forensic + OBA), `key_person` (8 tasks, no forensic/OBA), `extended_team` (3 tasks: preliminary-search, generic, employment-history only). Downstream tasks (regulatory-compliance/reputation/governance/forensic/OBA) inject prior outputs as `prompt_append` context.

**Source of truth for the dependency graph.** Both this person-research DAG and the fund-research DAG (§8) are generated, not hand-maintained separately in each runtime: `mix research.generate_dag` (`lib/mix/tasks/research/generate_dag.ex`) defines every research task (person and fund), its source schema, and its `depends_on` edges (with `scope`/`resolution: strict`/`injectAs: prompt_append` semantics), then writes the same graph out to both `config/research_dag.json` (consumed Elixir-side) and `src/config/research-dag.ts` (consumed by Trigger.dev) — a codegen step that keeps the two runtimes' understanding of task ordering in sync.

---

## 7. People Deep Research

**Execution.** `personResearchWorkflow`, per person, per role tier (§6). Phases (`workflow-phases.ts`): (1) context agents query the fund's shared Gemini File Search store for relevant upstream outputs (cached via `computeLlmCacheKey`), (2) a "Master Biographical Profile" agent grounds against internally uploaded documents, (3) research dispatch — `preliminarySearchAgentTask` for the first pass, `deepResearchTask` for the rest, batch-triggered across the person's tier.

**Providers.** `dispatcher.ts` routes to **Jina** (default, autonomous multi-page crawl, `reasoning_effort`/`token_budget` params) or **Exa** (`exa-research/-research-fast/-research-pro` tiers by effort). Internal knowledge base is queried first (`queryTaskResponse`) to prepend verified facts before dispatching external search. Exa extracts `references`/`visitedURLs`/`readURLs`; Jina runs a schema-constrained call plus a parallel markdown-only call. Report tone normalized post-hoc.

**Consolidation (`compile-person-dossier`).** Two dossiers merged: Dossier 1 (Gemini context-cache synthesis of all structured JSON reports, converted to markdown via `jsonToCustomMarkdown`), Dossier 2 (Gemini File Search "Interactions API" over raw source documents with citation extraction). Final merge follows a template with hard rules: comprehensiveness over summarization, preserve all quotes/citations, dedupe *only* on direct factual duplicates, mandatory "Source Audit & Report Map" section tying every fact back to its source. No numeric confidence score — verification is qualitative (reasoning strings + source audit); forensic red flags surface as dedicated sections. Output includes `masterProfile`, `individualReports`, run/citation metadata, files persisted to Tigris plus an FTS parquet index.

---

## 8. Fund Deep Research

Two parallel systems: a generic baseline task set (every fund, every asset class) and asset-class-specific "mission" packs (PE/PC/RE-specific `.toml` files, mirrored at runtime to `data/research/prompts/external_prompts/fund/`).

**Baseline set (6 core + 2 extended tasks), `fund-deep-diligence.ts`:**
- `strategy-thesis` — thesis verification vs. external evidence
- `performance-returns` — IRR/MOIC/DPI/TVPI verification against benchmarks, undisclosed drawdowns
- `regulatory-disclosures` — SEC EDGAR/IAPD, ERA/RIA status, Form ADV/D extraction
- `infrastructure-service-providers` — background checks on auditor/administrator/prime broker/counsel (depends on regulatory-disclosures)
- `competitive-benchmarking` — peer positioning (depends on strategy + performance)
- `governance-adverse-media` — key-man/LPAC structure, litigation/bankruptcy/settlement search
- Extended: `market-research`, `competitor-analysis`

**Asset-class mission packs:**
- **Private Credit** (4 missions, all Jina, 1M token budget, high reasoning): `fund-mechanics-baseline`; `legal-odd` (lender-liability/intercreditor litigation, state lending-license/usury compliance, lien priority/UCC/collateral perfection, warehouse-line margin-call/leverage risk, outputs a "breaking point thresholds" table + investigation methodologies checklist); `market-and-sector-dd`; `team-pedigree-dd`.
- **Real Estate** (4 missions, same shape) — tuned for REPE equity strategies (`fund_classifications: Real Estate Private Equity, REPE`).
- **Private Equity** (7 missions, richer metadata): deal-attribution/scalability audit; macro capital-overhang risk; human-capital-continuity assessment; institutional litigation audit; skeptical strategy verification (2M token budget); regulatory/SEC-action audit; employment/HR-risk audit; reputational-risk/background audit — organized under an explicit `category` taxonomy: Track Record & Performance / Strategy & Market Verification / Team & Human Capital / Legal & Regulatory Compliance / Reputational & ESG Risks.

Every mission file carries `meta.knowledge_agent_guidance` (target metadata categories, key search phrases, example queries) that grounds the deep-research prompt against internally uploaded documents (pitch deck/LPA/Form ADV) before hitting the open web.

**Dispatch architecture.** `dispatcher.ts` (`executeDeepResearch`) picks a provider, optionally grounds via internal knowledge base, runs deep research, then LLM-sanitizes the answer into both JSON and Markdown. `fund-deep-diligence.ts` builds a flat batch across entities (fund + GP/management company, up to 10 parallel) and principals (up to 10 parallel × 20 prompts parallel), firing everything in one `batchTriggerAndWait` call. `single-fund-research-mission.ts` runs mission packs one at a time, keyed by `assetClass/missionId`. Idempotency keys are hashed from date + task identifier + entity-name hash + token budget to prevent duplicate spend on reruns.

**Critical Audit Gap Analysis (`critical-audit-gap-analysis.ts`).** Automated "skeptic" step, run once per entity after baseline research is consolidated. Feeds the full dossier into an LLM against `diligence_analysis.schema.json`, inspecting five focus areas: Performance Blind Spots (missing IRR/MOIC/DPI), Structural Omissions (fee/hurdle/AUM gaps), Operational Risk (undisclosed Tier-1 service providers), Regulatory/Compliance Nuance (missing lawsuits/SEC actions), Data Staleness (metrics >2 quarters old). An "Emerging Manager Protocol" variant activates when `isEmerging` is true. Output (`redFlagsDetected`, `caseNumbers`, `tier2ServiceProviders`, `missingDataForWebSearch`) drives conditional Phase-3 follow-up tasks (regulatory-deep-dive, per-case-number forensic docket search, per-provider reputation check, recursive-deep-search) that re-enter the batch pipeline.

**Consolidation & sync-back.** `consolidateFundTask` merges all task outputs into a "FORENSIC MASTER DOSSIER" markdown with a fixed structure: Executive Summary, Key Personnel/Alignment/LP Base, Strategy & Thesis, Historical Performance, Regulatory Filings, Operational Infrastructure, Competitive Landscape, Governance & Adverse Media, "Blind Spots" (using `<critical_failure>`/`<unverified>` markup tags), Source Audit/Report Map. `sync-research-responses.ts` uploads every individual raw report plus citations to Gemini File Search stores and Tigris, tagged with metadata, and exports run metadata to Parquet — this file-based sync, not a relational DB write, is how the Elixir side reads results back.

**Providers/schemas.** Jina (default) and Exa (research/research-fast/research-pro tiers) via `dispatcher.ts`; lighter `quick-search.ts` (Jina Search API) backs preliminary search. Key schemas: `deep_research_payload/response.schema.json`, `diligence_analysis.schema.json`, `verification_checklist.schema.json`, `fund_website_analysis/verify_fund_website.schema.json`, `consolidated_team.schema.json`.

---

## 9. Scoring & Rubric Analysis

**Architecture.** The rubric is a **matrix of (dimension slot) × (asset class)**, stored as data — TOML files, not code. ~57 files named `score-<Letter><Number>-<slug>.toml`.

**Four categories (letters), display-priority order (`category_rankings.json`):**
- **A — Operational Quality & Viability** (ranking 1): manager/team pedigree & integrity, track-record plausibility/alpha quality, strategy/thesis quality & durability, domain validity/drawdown-tail-risk management, structural red-flag/LP-alignment assessment (fees, GP commit, waterfall, key-person clause)
- **B — Investment Sourcing & Value Creation** (ranking 2): idea generation/sourcing/origination, underwriting/acquisition/portfolio construction, execution (100-day plans, covenant negotiation, leasing, trade execution), exit/disposition/risk management/portfolio monitoring
- **C — Capital & Risk Mechanics** (ranking 3): leverage/capital structure, sizing/concentration (geographic, tenant, tranche), deployment pacing/development risk/counterparty risk, correlation/rate/currency/NAV-loan risk
- **D — Fund Operations & Compliance** (ranking 4): valuation policy/mark-to-market/co-investment dynamics, compliance & regulatory framework/conflicts of interest, cyber security/ESG/trade allocation/syndication, back-office/fund administration

Each letter has up to 5 numbered slots (A1-A5, B1-B4, C1-C4, D1-D4), and each slot has **multiple asset-class-specific variants** — e.g. slot B1 has separate files for Real Estate ("asset-sourcing-acquisition"), Hedge Fund ("idea-generation-research-process"), and PE/VC/Credit/Infra ("sourcing-origination"). `full-scoring-workflow.ts` (`src/trigger/scoring/agents/full-scoring-workflow.ts`, task `workflow-full-scoring`) is the sole live orchestrator — reads all 57 files, matches each `constraints.asset_class` array against the fund's normalized asset class, groups matched configs by letter (regex `/^score-([A-D])/i`), and dispatches **at most 4 category-level tasks** (fewer if a category has zero matched dimensions for that asset class) via `scoreCategoryAgent.batchTriggerAndWait`.

**Asset-class fuzzy matching — confirmed real and load-bearing.** `cleanString()` (`full-scoring-workflow.ts` lines 64-70) lowercases and strips non-alphanumerics from both the TOML's `constraints.asset_class` values and the fund's classified asset class, then special-cases two aliases: `hedgefund → hedgefunds`, `privatedebt → privatecredit`. Verified against actual TOML data — constraint values are stored plural/capitalized (e.g. `"Hedgefunds"` in `score-A1-manager-team-pedigree.toml`), confirming the normalization step is necessary, not defensive boilerplate. `src/trigger/agents/score-agent.ts` (`scoreDimensionAgent`) has a near-duplicate copy of this matcher that has **drifted** — it's missing the `privatedebt→privatecredit` alias — but this doesn't matter in practice: `score-agent.ts` has zero call sites anywhere in the codebase. It's dead code, an abandoned single-dimension (non-batched) fork of the same two-pass logic that `score-category-agent.ts` alone now implements live.

**Scale.** Fixed 5-tier ordinal scale for every dimension, defined once in the shared schema: `Exemplary → Strong → Adequate → Weak → Unacceptable` — no numeric weights (legacy scales explicitly forbidden per `scoring/Agents.md`). `Unacceptable` frequently doubles as a **VETO TRIGGER** written directly into the rubric text (e.g. "Missing Key Person Clause / No Management Fee Offset / Fraudulent Service Providers") — hard-fail conditions live inside the qualitative rubric rather than a separate rule engine.

**TOML anatomy.** `id` (UUID), `guidelines`/`prompt` (rubric text, templated with `{{fundName}}`), `schema` (`ModuleResponseSchema`), `category` (A/B/C/D), `ranking` (position within category), `name`, `examples`, `[constraints] asset_class = [...]`.

**Execution — dual-analyst-then-synthesize pattern, exact call count.** Each category task bundles every matched dimension's rubric into one combined prompt, then makes **3 Gemini calls, not 1**:
1. Pass 1a and Pass 1b run in parallel (`Promise.all`) — both actually call `gemini-3.1-flash-lite` over the fund's document store via file-search grounding: one lenient/deep-context, one instructed as a "strict, ruthless compliance analyst" that must mechanically apply thresholds without benefit of the doubt (breached limit ⇒ must assign that tier even if the fund beat benchmark elsewhere; missing clause ⇒ graded per rubric). Both output markdown (Qualitative Explanation / Evidence / Data Gaps / Red Flags), capped at 10 (single) or 20 (category-batch) search queries, with a `[NO_RELEVANT_DATA_FOUND]` escape hatch. Note: the prompt text itself labels these two passes "3.1-Pro" and "2.5-Pro" (`score-category-agent.ts` lines 289-293) — leftover copy from an earlier version that actually used two different models; both passes call the same `gemini-3.1-flash-lite` model today, so the "dual model" framing in the prompt is stale, even though the dual-*pass* structure is real and functioning.
2. Pass 2 — a synthesis call ("Senior Investment Analyst") reconciles the two analysts, emits final structured JSON: `score_category` (5-tier enum), `confidence_score` (0-100), `evidence[]`, `qualitative_explanation`, `data_gaps[]`, `red_flags[]`, `one_line_verdict`, `citations[]`, `synthesis_notes` (internal-only, documents conflict resolution).

**Total cost of one scoring run:** up to 4 category tasks × 3 calls each = **up to 12 Gemini calls per fund**, not "one call per category" — the batching is at the task level (one dimension-bundling task per category), not the LLM-call level.

**A wiring gap, analogous to the one found in L1 (§10).** `master-workflow.ts` calls `fullScoringWorkflow.triggerAndWait` with only `fundName`, `fundId`, `workflowRunId`, `masterData`, `teamData`, `isDryRun` — it does not pass `fileSha256`, `kbStoreName`, or `cacheControl`, all of which the payload type accepts and are used for idempotency/store-reuse. Concretely: omitting `fileSha256` means the per-run idempotency key always resolves its file-hash segment to the literal string `"no-sha"` (`src/lib/idempotency.ts`), collapsing that part of the dedup mechanism to a constant; omitting `kbStoreName` forces a fresh file-search store lookup instead of reusing one resolved earlier in the pipeline. More significantly: **the SEC/deep-diligence output computed one step earlier in `master-workflow.ts` (`ddResult`, Step 3) is never included in the scoring payload at all** — scoring receives only `masterData`/`teamData` from deck extraction, not the diligence findings sitting right next to it in the same workflow run. Worth fixing alongside the L1 `consolidatedKnowledge` gap — both are the same underlying pattern: a later stage's payload type supports richer upstream context than `master-workflow.ts` actually wires through.

**Quantitative breaking-point tables.** `repe-breaking-points.json` — Real Estate PE specifically — keyed by risk profile (Core/Core-Plus/Value-Add/Value-Add-Conversion/Opportunistic) × property type (Class A Multifamily, Grocery-Anchored Retail, Prime Industrial, Trophy CBD Office, Data Center, Student Housing, etc.). Each combination carries expected cash-on-cash yield, DSCR multiple, net IRR, LTV ranges, an economic-outlook block (treasury yield, SOFR, fed funds, CPI, GDP growth benchmarks), and `breaking_point_thresholds` (hard min/max cutoffs, e.g. DSCR min 1.2x, LTV max 65%, min net IRR 5%, min CoC 3.5%). Functions as reference data consulted during prompting, not a hard programmatic gate — a quantitative-threshold layer complementing the qualitative VETO triggers. This file isn't hand-edited: `mix decode_repe_matrix` (`lib/mix/tasks/decode_repe_matrix.ex`) decodes a real-estate-PE "Strategy and Financial Metrics Matrix" CSV (an external, dated source, tracked by an `as_of_date` outlook column) into this JSON — so the breaking-point thresholds are meant to be periodically refreshed from updated market data, not a static one-time table.

**No numeric roll-up.** `fullScoringWorkflow` collects per-dimension categorical results into `report.scores[]`, generates a markdown report per category, uploads it, POSTs to `/api/webhooks/score_sync`. The Elixir side maps dimension codes (A1, B2, etc.) to human labels from a hardcoded 20-item `flat_dims` list (which assumes exactly A1-A5/B1-B5/C1-C5/D1-D5 — slightly diverges from the actual variable-per-asset-class file set) and stores each as a `create_score` row keyed by `document_id`/`dimension`/`run_id`. `category_rankings.json` governs *display order*, not a scoring formula — there is no weighted composite anywhere.

---

## 10. L1 Analysis (Final Investment Committee Output)

**Format.** Not a slide deck — a structured JSON object (`L1AnalysisSchema`) rendered as a Phoenix LiveView **web document** with 10 scrollable sections (anchors `#l1-verdict`, `#l1-exec`, etc.) — an IC memo web page.

**Orchestrator.** The real orchestrator is `l1AnalysisWorkflow` in `src/trigger/pitch-deck/workflows/l1-analysis-workflow.ts`. (`src/trigger/pitch-deck/l1-analysis.ts`, despite the name, only holds Zod schema definitions — `VerdictSchema`, `ExecutiveSummarySchema`, `L1AnalysisSchema`, etc. — no orchestration logic lives there.) It loads component definitions from `l1/definitions/analysis/*.toml` (5 top-level files + a `modules/` subfolder of 4) and `l1/definitions/agenda/*.toml` (5 files). Note: `agents/definitions/l1_presentation/{analysis,agenda,schemas}/` is a parallel, near-identical directory that exists on disk but the workflow never actually reads from it — it's only referenced as an unused default parameter. Treat it as stale/legacy, not the live source.

**Total cost of one memo.** Generating one L1 memo fans out to **14 top-level agent invocations** (9 `l1PresentationAgentTask` calls covering Verdict/Executive Summary/Claims Ledger/Flags/Asks + 4 Modules, plus 5 `generateMeetingAgendaItemTask` calls, one per agenda topic), each of which makes 2-3 sub-model calls internally — roughly 30+ raw LLM requests per memo. Two sections (Fund Factsheet, Scoring Dimensions) are **not** part of this fan-out at all — see below.

**Section-by-section generation:**

1. **Verdict** — dedicated call. `l1/definitions/analysis/verdict.toml` (`schema="VerdictSchema"`) → `l1PresentationAgentTask` → `decision` (ADVANCE/DECLINE/CONDITIONAL), `verdict_summary`, `what_would_change_our_mind[]`.
2. **Executive Summary** — dedicated call. `l1/definitions/analysis/executive_summary.toml` → same task → narrative + `key_strengths[]`/`key_risks[]`.
3. **Fund Factsheet** — **not an LLM call.** Built deterministically, zero LLM calls, by `mapPrivateMarketSchema()` (`src/trigger/pitch-deck/mappers/master-schema-mapper.ts`) during the earlier deck-extraction stage (§4), which normalizes fields straight out of `consolidatedKnowledge` — currency/percentage/year parsing helpers, no generation. It runs upstream of and independently from `l1AnalysisWorkflow`; the L1 memo just displays what extraction already produced.
4. **Claims Ledger** — two-stage. `runVerificationChecklistAgent()` (part of the separate fund-deep-diligence pipeline, §8 — not `l1AnalysisWorkflow`) makes 4+N sequential/parallel `gemini-3.1-flash-lite` calls to extract falsifiable claims (fund claims, one call per person, company claims). Separately and later, `l1/definitions/analysis/claims.toml` (`schema="ClaimsSchema"`) drives its own standard `l1PresentationAgentTask` call, intended to be fed the verification results via `consolidatedKnowledge` — array of claims each with `status` (CONFIRMED/CONTRADICTED/UNVERIFIABLE), `level` (INFO/WARNING/CRITICAL/NOTE), evidence, citations.
5. **Flags & Questions** — dedicated call. `l1/definitions/analysis/flags.toml` (`schema="FlagsSchema"`) → severity-ranked (CRITICAL/WARNING/INFO) flags with `questions_to_ask[]`.
6. **Scoring Dimensions** — **entirely separate pipeline**, not part of `l1AnalysisWorkflow` at all. This is the full §9 output (`fullScoringWorkflow`), run as its own step (Step 4) in `master-workflow.ts`, sibling to — not merged into — the L1 step (Step 5). The L1 memo's Scoring Dimensions section is a display of that already-completed, independently-run result.
7. **Modules** (`investment_strategy`, `team`, `operational_infrastructure`, `track_record`) — 4 separate TOML-driven calls, same mechanism as Verdict/Flags. Each `l1/definitions/analysis/modules/*.toml` sets `schema="ModuleResponseSchema"` uniformly, plus its own `category`/`ranking` (e.g. `team.toml`: category "Operational Due Diligence", ranking 1) and an optional `constraints.asset_class` that skips the module for asset classes it doesn't apply to. Results are collected and sorted by `ranking`. Different 4-tier scale (STRONG/ADEQUATE/WEAK/FLAGGED) from the scoring section's 5-tier scale. Currently scoped to Private Equity/Hedgefunds/Venture Capital.
8. **Asks & Materials Requests** — dedicated call. `l1/definitions/analysis/asks.toml` (`schema="AsksSchema" = {standalone_asks[], materials_requests[]}"`) → one call, one schema, the workflow splits the single response into the two output arrays.
9. **Meeting Agenda** — confirmed **one call per topic** (5 total), via a *different*, simpler agent: `generateMeetingAgendaItemTask` (`src/trigger/agents/meeting-agenda.ts`) — single-analyst (`gemini-3.1-flash-lite`) 2-pass flow, not the dual-analyst pattern, and its payload schema doesn't even accept `consolidatedKnowledge`. Fires as 5 independent `batch.triggerByTaskAndWait` calls, one per `l1/definitions/agenda/agenda-{1..5}-*.toml` file (concentration/drawdown, key-person/succession, underwriting/valuation, AUM capacity/scaling, operational institutionalization), each with `[examples]` strong/weak answer exemplars for calibration.
10. **Sources** — not a standalone call; a derived artifact. Every `l1PresentationAgentTask` and `generateMeetingAgendaItemTask` call returns `citations` from its Gemini file-search grounding annotations; the workflow accumulates these per-component into `l1_analysis._citations`. There is no dedicated "sources" agent — the Sources section is the union of every other section's own grounding citations.

**Common mechanics of `l1PresentationAgentTask`** (drives 9 of the 14 calls — Verdict, Executive Summary, Claims Ledger, Flags, the 4 Modules, Asks). Fully generic and config-driven: nothing in the code is section-specific except the injected TOML config and the dynamically-loaded output schema named by `config.schema`. Per call: Pass 1a `gemini-3.1-pro-preview` ("Analyst A", deep-context) + Pass 1b `gemini-2.5-pro` ("Analyst B", strict-quant) run in parallel over the fund's Gemini file-search store (each capped at 10 search queries, `[NO_RELEVANT_DATA_FOUND]` escape hatch); Pass 2, `gemini-3.1-pro-preview`, synthesizes both analysts' markdown plus `consolidatedInfo` into the section's JSON schema. Strict prompt rules keep client-facing text free of internal artifacts (never "The Team and Key-Man Risk module presents...").

**A real wiring gap.** The dual-analyst pattern is designed to receive `consolidatedKnowledge` — the already-computed scoring and claim-verification results, injected so the memo builds on prior judgments rather than re-deriving them independently (documented as the intended design in the original version of this section). In the current code, however, `master-workflow.ts` Step 5 calls `l1AnalysisWorkflow.triggerAndWait` **without actually passing `consolidatedKnowledge` or `scoreResult`**, even though the schema accepts both. In practice, every `l1PresentationAgentTask` call today runs with an empty `consolidatedInfo` block — each section is generated from file-search grounding alone, not from the upstream scoring/claims data the design intends. Worth flagging as a fix: wiring `scoreResult` and the claims-verification output through Step 5's payload would make the memo's Verdict and Modules sections actually reflect the Scoring Dimensions section sitting right next to them, rather than being derived independently and potentially disagreeing with it.

---

## 11. Gemini — How Reasoning Is Actually Used

Gemini (`@google/genai`) isn't one call per document — it's layered into five distinct usage patterns across the pipeline, each suited to a different kind of task.

**Pattern 1 — Native structured output.** Every extraction and classification call sets a strict `responseSchema` (`responseMimeType: application/json`), built by converting the app's own Zod schema to JSON Schema (`zodToJsonSchema`). The model cannot return free text — only the exact fields defined in the schema. This is used for document classification (§2), fund classification (§3), every extraction schema (§4), key-principal verification (§6), and the final structured output of every scoring/L1 call (§9-10).

**Pattern 2 — Two-step "text first, structure second."** For every extraction schema (not just classification), the pipeline never asks Gemini to read a raw PDF and emit JSON in one shot. Instead:
1. `generateContent` with a `fileData` part (the raw PDF via Gemini Files API) → a comprehensive markdown report, with the prompt forcing verbatim quoting and page citations (`[Page X]`)
2. A second, separate `generateContent` call over that markdown, this time with `responseSchema` set → structured JSON

This exists specifically to stop the model from inventing or miscalculating numbers while simultaneously trying to read a document and format JSON — reading and structuring are deliberately split into two calls.

**Pattern 3 — Extract-then-normalize for every number.** Layered on top of Pattern 2: every monetary/percentage/duration/multiplier field first captures a `source_number_text` string verbatim ("$500K", "2.5x", "18 months"). A separate, smaller model call (`gemini-3.1-flash-lite` via `llm.generateJson`, `parseMeasurementsInPayload` in `schema-extraction.ts`) then parses that string into `{amount, magnitude: ONES|HUNDREDS|THOUSANDS|MILLIONS|BILLIONS|TRILLIONS}` or a range. No arithmetic ever happens inside the same call that's reading prose.

**Pattern 4 — Per-fund File Search grounding (RAG).** The moment a document is classified (§2), a Gemini File Search Store is opened for that fund and every subsequent document (pitch deck, SEC filings, research reports) is uploaded into it. Every later stage — scoring analysts, L1 section generation, person/fund research context agents — queries this store first via file-search-grounded `generateContent` calls, so judgments are made against the fund's actual uploaded paperwork with citations, not from the model's general knowledge. `internal-research-context-agent.ts` and `queryTaskResponse` are the mechanisms that query this store before falling back to open-web research (§7-8).

**Pattern 5 — Dual-analyst-then-synthesize.** Used for every scored criterion (§9) and every L1 memo section (§10):
1. Two parallel analyst calls over the file-search store — one lenient/deep-context, one instructed as a "strict, ruthless compliance analyst" that must mechanically apply thresholds with no benefit of the doubt. Both are capped at 10-20 search queries and can return `[NO_RELEVANT_DATA_FOUND]` instead of guessing.
2. A third synthesis call ("Senior Investment Analyst") reconciles the two into final structured JSON with evidence, confidence, data gaps, and red flags.

**Model tiering.** `gemini-3.1-flash-lite` handles high-volume/cheap calls (document classification, numeric normalization, key-principal verification, both scoring-analyst passes). `gemini-3.5-flash` (thinking: high) handles the heavier per-schema extraction and fund classification. `gemini-3.1-pro-preview` + `gemini-2.5-pro` (dual pass) handle the L1 memo's analyst stage, with `gemini-3.1-pro-preview` alone doing the synthesis — the most expensive, highest-stakes calls in the pipeline are reserved for the final client-facing output.

---

## 12. Jina + Exa — How Web Research Is Actually Used

When a claim can't be resolved from the fund's own uploaded documents (Pattern 4 above), the pipeline leaves the private knowledge base and searches the open web through a single dispatcher (`src/trigger/research/provider.ts` → `dispatcher.ts`, `executeDeepResearch`/`deepResearchTask`) shared by every person-research and fund-research task.

**Dispatch order.** For every research task: (1) query the fund's internal Gemini File Search store first (`queryTaskResponse`) — if the fact is already verified from an uploaded document, that's used and no external call happens; (2) if not found, the dispatcher routes to a provider based on the task's `provider` field (defaults to Jina); (3) the raw provider output is passed through a Gemini cleanup call that strips citation-ID artifacts, normalizes tone, and re-cites — so every downstream report reads uniformly regardless of which provider produced it.

**Jina — the default provider.** `jina/deepsearch.ts` (`performJinaResearch`) runs an autonomous, multi-page web crawl per research question, tuned by `reasoning_effort` and `token_budget` parameters (person research: 1M token budget, high reasoning; some PE fund missions go to 2M). Two calls fire per task: one schema-constrained (forces the response into the task's output schema) and one parallel markdown-only call — so information that doesn't cleanly fit the schema isn't silently dropped. A lighter sibling, `quick-search.ts` (Jina Search API), backs `preliminarySearchAgentTask` — a fast snippet-level sweep used for initial disambiguation before the heavier deep-research calls run.

**Exa — the alternate provider.** `exa/deepsearch.ts` (`performExaDeepResearch`) is used where a task explicitly requests it. Effort maps to three tiers: `exa-research-fast`, `exa-research`, `exa-research-pro`. Every Exa response returns its actual source list — `references`, `visitedURLs`, `readURLs` — which feeds the citation trail directly, whereas Jina's citations come from the cleanup pass's re-citation step.

**Where each is used.** Person research (§7) and fund research (§8) both call the same dispatcher for every task in their respective taxonomies (10 categories for people, 6+2 baseline + asset-class mission packs for funds) — the provider choice is a per-task configuration, not a stage-level architectural split. `acquireL1SecDocumentsTask` (§5) also falls back to a Jina web search when entity categorization can't be resolved from the internal knowledge base.

**Idempotency and scale.** Every triggered research task gets an idempotency key hashed from `date + taskIdentifier + entity-name hash + token budget`, so re-running an analysis within the same day doesn't re-spend on identical research. `fund-deep-diligence.ts` batches aggressively — up to 10 entities in parallel × up to 10 principals in parallel × 20 prompts in parallel — all fired in a single `batchTriggerAndWait` call rather than sequential loops, which is what keeps a full diligence pass to hours rather than days.

---

## 13. The Fund Dashboard — Sidebar Panels

Everything above is the pipeline. This section documents the operator-facing UI that sits on top of it — the fund-detail workflow screen, whose sidebar is `DealsAnalysisWeb.PitchDeckWorkflowProgressLive` (`lib/deals_analysis_web/live/pitch_deck_workflow_progress/`). Most items are tabs inside this one LiveView (`?tab=` query param, socket stays alive on switch); **Gemini Store** and **Agent Inspection** are standalone LiveViews at their own routes. L1 Analysis, SEC Data, People, Fund Deep Research, and Scoring are covered in §5-10 above — they're tabs on the same screen, reading the outputs of those respective stages.

**Fund Intelligence** (`pitch_deck_summary/1`) — the polished, read-only "final answer" view of everything extraction (§4) produced: `document.parsed_data`, `document.master_data`, and `sec_data` rendered as numbered magazine-style sections (Overview & Model, Leadership/Team, Strategy & Focus, Track Record, Pipeline, Analyst Disclosures). Distinct from the L1 memo — this is the raw structured facts, not the IC-facing synthesis.

**Slide Analysis** (`SlidesTabComponent`) — a QA tool for verifying what the AI actually extracted per slide, toggled between two views: "Extracted Data" (structured per-category results tied to the rasterized page images from §2) and "OCR Slide Data" (raw per-slide markdown/OCR text with annotations). Includes "Consolidated MD" / "Consolidated JSON" export buttons for the full deck.

**Workflow Status** (`WorkflowStepperComponent` + `TriggerLogsComponent`) — the ops/monitoring view of the `workflow-master-fund` orchestration described in §2: a vertical stepper (upload → page conversion → parsing → asset-class classification → extraction → SEC diligence → team research → …) with live per-step status (pending/current/completed/failed) computed from `WorkflowProgressHelper.workflow_steps/3`, plus a live execution log console underneath. Two operator actions live here: **"Dry Run Full"** re-triggers the entire pipeline from scratch; each individual step also supports **"rerun_task"**, mapped to a specific Trigger.dev task identifier (`workflow-process-pitch-deck`, `acquire-sec-diligence`, `find-fund-website`, `compile-target-research-team`, etc.) — so a single failed stage can be re-run without re-running the whole 4-hour pipeline.

**Custom Research** (`CustomResearchComponent`) — the one panel that's a trigger UI rather than a viewer. An operator defines a named research topic (extraction prompt, system prompt, research prompt), saves it as a `custom_research` Ash record, then fires it via one of two actions: `run_custom_agent` (grounds against the fund's Gemini File Search store — an ad hoc version of §11 Pattern 4) or `run_custom_research` (a full open-web deep-research call — an ad hoc version of §12), each with a `force`/no-cache override. This is the escape hatch for "the standard pipeline didn't ask this specific question — ask it now."

**Gemini Store** (standalone `DocumentGeminiStoreLive`, `/funds/:id/gemini_store`) — an ops/debug window into the raw Gemini Files API usage backing §11 Pattern 4. Lists every uploaded Gemini file reference (display name, `gemini_file_id`, size, which pipeline task uploaded it, expiration state), filterable by search/task/status, plus the grounding queries run against those files (prompt, response, structured `response_data`). Notable action: **"sync_metadata"** per file, which calls the live Gemini API to refresh expiration state or mark a file `EXPIRED` if it's gone from Google's side — useful because Gemini Files auto-expire after a fixed window, and this is how staleness gets caught.

**Agent Inspection** (standalone `DocumentAgentsLive`, `/funds/:id/agents`) — a read-only trace/observability view over every autonomous agent call the pipeline made for this fund (the `Agent` Ash resource), filterable by pipeline run, search, and status. Clicking into one agent shows its full conversation turns and tool calls, each with an async LLM-generated summary — this is the debugging tool for "why did the scoring/research agent conclude X," letting an operator replay exactly what the model saw and did. A second tab lists the Gemini file-search vector stores and their indexed documents directly.

**Website Extraction** (`website_research_dashboard`) — shows the output of the `find-fund-website` task: visited URLs, search queries run, SEC-sourced vs. deck-sourced website candidates, extracted `fundData`, and any team members sourced specifically from the website (tagged "(Website)" in the unified team list) rather than the deck. Has its own "Trigger Execution Logs" sub-tab and a "rerun_task" button scoped to just this task.

**Task Logs** (`TriggerLogsComponent`, standalone from the stepper) — a raw, terminal-styled console of the Trigger.dev run log: task identifier, version, per-attempt start/success/error events with durations. Links out to a full-log view (`/funds/:id/workflow/log/:run_id`) for the complete record. Pure ops console, no interactive actions beyond that link.

**Debug Payload** (`system_debug_view` + `l1_debug_layout`) — a syntax-highlighted, pretty-printed dump of the raw JSON a workflow run actually produced (`document.parsed_data`, falling back to the raw `trigger_full_run["output"]`), with a "Copy Raw JSON" button, plus a second sub-tab reusing the L1 debug layout. The tool of last resort when diagnosing an extraction bug — this is what the raw model output looked like before any of the rendering in §3-10 happened to it.

---

## 14. The Elixir ↔ Trigger.dev Bridge

Every stage described in §1-10 runs as TypeScript in Trigger.dev, while state, storage orchestration, and the UI live in Elixir. `lib/trigger_dev/client.ex` is the seam between them, and carries real operational logic beyond "make an HTTP call":

- **`trigger_task/3`, `batch_trigger_task/2`, `get_run/1`, `cancel_run/1`, `trigger_and_wait/4`** — the last polls with exponential backoff (1s → 5s) rather than a fixed interval, so short-running tasks resolve quickly without hammering the API on long ones.
- **Large-output handling.** `get_run/1` transparently follows `outputPresignedUrl`/`outputUrl` when Trigger.dev has offloaded a large task output to S3 rather than returning it inline, decoding the result via `TriggerDev.SuperJSON`. Callers never need to know whether a given run's output came back inline or via a redirect.
- **`get_deep_run/1`** recursively expands child runs for workflow/research/diligence task-identifier prefixes (`workflow-`, `fund-deep-diligence-`, `person-research-`, plus `deep-research`, `compile-person-dossier`, `gather-sources`, `build-knowledge-parquet`) — this is the actual run-tree model behind the Workflow Status and Agent Inspection panels (§13): a single top-level run fans out into dozens of child runs, and this is how the UI reconstructs that tree for display.
- **Environment routing.** The `preview` environment uses `TRIGGER_SECRET_KEY_PREVIEW` (falling back to the prod key if unset) and adds an `x-trigger-branch` header, so branch-based preview deployments hit isolated Trigger.dev environments without a separate secret per branch.
- **Shared file bus.** Every outbound payload from Elixir has `bucketName` (from `TIGRIS_BUCKET`) auto-injected — Tigris is the shared object-storage bus both runtimes read/write against, which is why neither side needs a direct RPC to move large files (decks, page images, research reports) between them.
- **Realtime status.** `lib/trigger_dev/realtime.ex` reimplements Trigger.dev's `useRealtimeRun` React hook for LiveView — polling every ~1.5-3s with terminal-state detection — and `sse_client.ex` provides an SSE alternative against `/realtime/v1/runs/:id`. This is what powers live-updating progress in the Workflow Status tab without a page refresh.

**Deploy model.** Trigger.dev workflows deploy independently of the Phoenix app (`npx trigger.dev deploy --env {preview,staging,prod}`), with secrets managed in the Trigger.dev dashboard rather than app `.env` files — the two runtimes are versioned and released separately, which is part of why the preview-branch header logic above exists (a Phoenix preview deploy and a Trigger.dev preview deploy aren't guaranteed to land at the same moment).

---

## 15. Knowledge Agent — Chat With Your Data

Separate from the Trigger.dev research pipeline (§7-8) that produces dossiers automatically, there's a live, interactive "chat with this fund's data" feature: `DealsAnalysis.Research.KnowledgeAgent` (`lib/deals_analysis/research/knowledge_agent/`), exposed at `/funds/:id/graph_explorer` (`GraphExplorerLive`). A user opens a fund's Graph Explorer page and types natural-language questions against that fund's extracted knowledge base and schema; the agent maintains a per-document chat history and routes each query through a selectable retrieval strategy, streaming "thought" messages (e.g. "Initiating Hybrid SIRA Search...") before returning an answer with an estimated token cost:

- **SIRA** (hybrid search with LLM query expansion, document-frequency-validated synonym candidates, reciprocal rank fusion) — searchable against either the "knowledge" database (document chunks) or "metadata" database (schema topics)
- **GraphRAG** — traverses a schema subgraph to answer conceptual questions
- **Vector (HNSW)** search with LLM query reformulation
- **Lexical (BM25)** — DuckDB full-text search with keyword extraction
- **Gemini File Search** — calls Google's Generative Language API directly against a named Gemini file-search store, returning grounded citations (the same underlying mechanism as §11 Pattern 4, exposed here as a user-selectable mode rather than a background grounding step)

**A real, currently-live correctness gap.** The Vector/HNSW mode is backed by `native/ruvector_nif` — a Rust NIF (via Rustler, wrapping the `ruvector-core`/`ruvector-graph` crates) exposed as `DealsAnalysis.VectorDB.Ruvector`, reading a compiled index built from schema metadata (not deal content) synced from Tigris by `SchemaDbSync`. In the running app today, however, **`DealsAnalysis.VectorDB.RuvectorServer` is never started** — it's absent from `application.ex`'s supervision tree. Every caller (`KnowledgeSearcher.search_metadata`, `IdentifyKeysAction`) guards with `GenServer.whereis/1` and silently falls back to BM25/lexical search whenever the process isn't running — which, as deployed, is always. The Vector/HNSW option in the UI is fully implemented but functionally dead; selecting it produces a lexical-search result, not a semantic one, until the GenServer is added to the supervision tree. Worth flagging as a fix, not a feature to describe as working.

(Separately: the "RuVector" persona name used elsewhere in `GraphExplorerLive`/`RuvectorAgent` is a naming artifact — that code path prompts an LLM over a raw Cypher-text graph string and does not call the Ruvector NIF at all, despite the shared name.)

---

## Infrastructure Notes (Provisioned, Not Yet Load-Bearing)

A few pieces of infrastructure exist in the codebase but aren't currently doing work in the live pipeline — worth knowing about so they aren't mistaken for active behavior:

- **FLAME / Hetzner elastic compute** (`lib/flame/hetzner_backend.ex`) — a custom `FLAME.Backend` for provisioning ephemeral Hetzner Cloud VMs on demand (boots, `git pull && mix compile && mix phx.server`, self-destructs via the Hetzner API on idle). A pool (`DealsAnalysis.HetznerRunner`, min:0/max:5) is started in `application.ex` when `HCLOUD_TOKEN` is set — but there are currently zero call sites (`FLAME.call`/`FLAME.place_child`) anywhere in the app. It's wired up and ready but nothing dispatches work to it yet; the actual "this needs a big dedicated machine" story in this codebase is the standalone `mix extract.irs_990` batch job (§5), not FLAME.
- **Bulk research admin tool** (`lib/deals_analysis_web/live/bulk_action_live/`, `lib/deals_analysis/research/bulk_action.ex`) — an admin UI for firing a batch of ad hoc research prompts (Jina/Exa, configurable reasoning effort/token budget) with poll/cancel-all/start-all-pending controls. This is a research-prompt experimentation surface, distinct from — and not to be confused with — a "re-run all funds through the pipeline" capability, which doesn't exist; reprocessing is always scoped to one fund/document at a time via Workflow Status's "Dry Run Full" or per-step "rerun_task" (§13).

---

## Explicitly Out of Scope

A few top-level directories were investigated and confirmed to contain **no live product logic** — noted here so they aren't re-flagged as documentation gaps in a future pass:

- **`stitch_investor_dashboard/`** — four static, AI-design-tool-generated (Stitch) HTML mockups (Tailwind-via-CDN, hardcoded placeholder data, no Phoenix/LiveView markup, no router references). Sketches a possible future LP/investor-facing dashboard; not wired into the app.
- **`conductor/`** — internal engineering planning/tracking scaffolding (plan docs, initiative archive). Documents how the team built the pipeline over time, not how the pipeline itself works.
- **`experiments/hei_structured_research/`** — an unmerged prototype research schema/prompt for Home Equity Investment (HEI) firms, a real-estate-finance asset class the platform doesn't currently support. Never referenced from `src/` or `lib/`.
- **`priv/native/redb.so`** — a compiled NIF for the `redb` embedded key-value store crate; no Elixir code references it. Orphaned build artifact.
- **`priv/resource_snapshots/`** — periodic JSON exports of DB tables, not read by any live code path; appears to be a manual/external backup process.

---

## Cross-Cutting Patterns Worth Noting

- **Extract-then-normalize**: verbatim text captured first, structured/numeric parsing done in a separate, smaller LLM call — used for both document classification fields and every measurement (money/percent/duration/multiplier).
- **Dual-analyst-then-synthesize**: every scored or generated judgment (scoring dimensions, L1 sections) runs two independent LLM passes with different postures (lenient/deep-context vs. strict/mechanical), then a third synthesis pass reconciles them into final structured output.
- **Rubric/task-as-data**: scoring rubrics and research task definitions live in TOML files, not code — new asset classes or research categories are added by writing a file, not shipping a deploy.
- **File-search grounding before external search**: every research/scoring/synthesis step queries the fund's Gemini File Search store (internally uploaded documents) first, so external web research/LLM judgment is grounded in — and can be checked against — primary source documents already in hand.
- **Fail-open on ambiguity, escape hatches on missing data**: role classification defaults to inclusion on parse failure; scoring/research prompts have explicit `[NO_RELEVANT_DATA_FOUND]`/data-gap fields rather than forcing a guess.
- **No numeric roll-ups anywhere**: scoring is categorical (5-tier), L1 modules are categorical (4-tier), and nothing aggregates into a single overall fund score — everything surfaces to the reader as-is, with display order (not weight) governed by `category_rankings.json`.
- **Idempotency by content hash**: SHA-256 of the file (uploads) or hash of date+task+entity+budget (research tasks) prevents duplicate storage/spend on reruns.
