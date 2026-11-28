# Prompts: build and verification session (Claude Code, cloud session)

Every message the student sent in the session that built, deployed, redesigned and verified the site,
in order. Messages are **verbatim** (spelling kept as typed), with three exceptions, each marked in
*[square brackets and italics]*:

- The full plan text, pasted twice into the first message, is not repeated here; it is saved verbatim in
  [`../01-plan.md`](../01-plan.md).
- Long passages copied from third-party web pages (news articles, vendor pages) are summarised rather than
  republished.
- Screenshots and uploaded files are described, since they cannot be shown as text.

The model was Claude (Opus 5.5) in Claude Code. The planning conversation that produced the plan (with
the clarifying questions recorded in the plan's §0) took place in an earlier session; its prompts are in
[`01-planning-session.md`](01-planning-session.md) if available.

The right-hand note says, in a few words, what the AI did in response; the details are in the git history
and in [`../03-decisions.md`](../03-decisions.md).

---

## Part 1: save the plan and build the site (milestones M0–M10)

**1.**
```text
[The approved plan "RO Desalination Explorer: Implementation Plan", pasted in full. Saved verbatim in 01-plan.md.]

Two things in the text are out of date now:

The Location row in §0 and step 1 of §7 describe a new local folder with git init. Since then you created DrewDebugs/RO-Explorer on GitHub and want it cloned into Documents, with me committing and pushing.
Repo and folder names in the file tree and the Pages URL use ro-explorer. Your repo is RO-Explorer, so the site URL will be https://drewdebugs.github.io/RO-Explorer/.

When I save it to the repo, should I correct those parts, or keep the approved text exactly as it was?

Print the full approved plan text here

[The approved plan pasted in full a second time.]
```
*AI: printed the plan as Markdown; recommended keeping it verbatim and recording later changes separately.*

**2.**
```text
Save the plan as docs/ai-log/01-plan.md, then commit and push it to the main branch of my GitHub repo DrewDebugs/RO-Explorer.
```
*AI: GitHub access was not linked yet; committed locally and explained how to connect GitHub.*

**3.**
```text
okay try now
```
*AI: cloned the repo and pushed the plan (first commit).*

**4.**
```text
Yes
```
*AI: M0 — README, CI workflow, smoke tests, decisions log; pinned Pyodide 314.0.7 / Python 3.14 / numpy 2.4.6.*

**5.**
```text
Yes
```
*AI: M1 — units, osmotic pressure (van't Hoff, Pitzer), temperature correction, SEC_min, with tests.*

**6.**
```text
Yes just finish it
```
*AI: M2–M10 — local solver, vessel model, energy and economics, SciPy reference implementation, validation checks, the page, the interactive app, browser testing and the Pages deploy workflow.*

**7.** *[A message reading "Tool loaded." appeared in the conversation at this point; it appears to have been sent automatically rather than typed.]*

**8.**
```text
> I haven’t checked the live URL yet. Once Pages is on, tell me and I’ll run a quick check on it.

How to turn on
```
*AI: steps to enable GitHub Pages (Source: GitHub Actions) and re-run the workflow.*

**9.** *[Screenshot of the repository's Actions page: run #7 "CI / Pages" green, the two previous runs red.]*

*AI: confirmed the deploy succeeded; the container could not open github.io, so asked the student to check the live site.*

**10.**
```text
where to find the website
```

## Part 2: ocean-themed redesign and industry examples

**11.**
```text
Make the website look way more graphically appealing based on RO and water/ocean themed
```
*AI: ocean redesign — hero with an animated pressure-vessel diagram, waves, key-numbers strip, osmosis diagram, new palette.*

**12.**
```text
add more ocean animations and graphics as well as make the mouse bubble
```

**13.** *[Sent while the previous request was in progress:]*
```text
Also add industry examples
```
*AI: bubble cursor with click ripples, fish, whale, jellyfish, seabed footer, scroll reveal; seven cited industry examples.*

## Part 3: checking every number against its source

**14.**
```text
great what is the next steps
```

**15.**
```text
* Start with the rows marked TODO-VERIFY. These are numbers I couldn’t confirm against a primary source:
   * the Pitzer parameters and the NaCl osmotic-coefficient table
   * the 1.06 kWh/m³ minimum-energy figure (Elimelech & Phillip 2011)
   * the 69 % RO share
   * the A and B permeance ranges
   * the economics unit costs
   * Taweelah’s solar share
   * the fab ultrapure-water figure
* For each one you confirm, remove its TODO-VERIFY badge in `index.html`, or ask me to. If a value turns out to be wrong, tell me the correct one and I’ll update the model, tests and page together. 

How do I verify these
```

**16.**
```text
Why do I have to verify these
```

**17.**
```text
how do I check the boxes
```

**18.**
```text
can you give me exact links to what I need to verfy
```

**19.** *[Screenshot of the UN World Ocean Assessment, Chapter 8: "Membrane desalination technology (involving reverse osmosis) accounts for approximately 85% of total worldwide desalination plants and generates approximately 69% of global desalination capacity …"]*
```text
fpor 4
```
*AI: verified the 69 % RO share (S33).*

**20.** *[Sent while the previous request was in progress:]*
```text
1-3 are also good same for the constant ones like s1
```
*AI: verified the Pitzer parameters, the osmotic-coefficient table, 1.06 kWh/m³ and the constants (S1–S6, S8, S39).*

**21.** *[Uploaded file: DuPont FilmTec SW30HRLE-440 product data sheet (PDF).]*

*AI: confirmed element area, length and the 83 bar limit; fitted A and B to the datasheet's standard test and offered three options for the defaults.*

**22.** *[Screenshot of the abstract of Ghaffour, Missimer & Amy (2013), with the US$0.50–1.00/m³ water-cost range. Pasted text from a pv magazine article (23 June 2022) on the Taweelah plant, quoting ACWA Power on its 909,200 m³/day capacity, a solar share of at least 30 % within eight years (target 55 %) and a solar park of about 69 MW. Pasted text from an MKS Instruments page on ultrapure water for semiconductor manufacturing, including the figure of up to 3,000 m³/day for a 200 mm fab.]*

*AI: verified S28, S43, S48 and reworded the Taweelah and semiconductor cards to match the sources.*

**23.** *[Uploaded file: FilmTec design equations and parameters, Dow Form 609-02057-604 (PDF). Sent after interrupting the AI's previous step.]*

*AI: verified the temperature correction factor, pressure drop and polarisation correlations; added two cross-checks to the theory section.*

**24.** *[Uploaded file: Schunke et al. (2020), "Energy recovery in SWRO desalination", Frontiers in Sustainable Cities (PDF).]*
```text
Option 3 and send like for economics
```
*[Followed, after an interruption, by:]*
```text
link
```
*AI: changed the default membrane to the datasheet fit (A = 1.4, B = 0.05, 12 m³/h); verified the ERD efficiency; sent links for the economics.*

**25.**
```text
b
```
*AI: calibrated the economics defaults to retail prices and an industry cost breakdown.*

**26.**
```text
links
```

**27.** *[Screenshot of the "U.S. Total" row of EIA Electric Power Monthly Table 5.6.A: 18.16, 17.57, 14.47, 13.87, 9.64, 8.98.]*

*AI: read the industrial price as 9.64 ¢/kWh and changed the electricity default from $0.08 to $0.096/kWh.*

**28.**
```text
mark them as stated assumptions and send me the rest with links I have to verify
```

**29.** *[Screenshot of a FilmTec design-guidelines table for 2.5-inch and 4-inch elements. Uploaded file: Jones et al. (2019), "The state of desalination and brine production: A global outlook" (PDF).]*
```text
I check all the economics numbers (2) and they are good.
```
*AI: verified the economics (S22–S26) and the global figures from the Jones paper (S29–S32); found the 69 % RO share in Jones as well.*

**30.** *[Uploaded file: FilmTec "Membrane System Design Guidelines", Dow Form 609-02054-0812 (PDF). Screenshots: ACWA Power "Who we are" page; IDE page stating Sorek 2 delivers 670,000 m³/day; page stating Sorek produces 624,000 m³/day.]*

*AI: verified Sorek and Sorek 2; found Taweelah's capacity in the earlier pv magazine quote; partly checked the feed flow.*

**31.** *[Screenshot of the FilmTec design-guidelines table for 8-inch elements, including seawater maximum feed flow.]*
```text
The numbers are correct for S37, S38, S44, S45, S46, S47
```
*AI: verified the feed flow against the 8-inch limits (S15) and the plant facts.*

**32.**
```text
> [ ] S41, membrane suppliers. Check that each company makes RO membranes:
>    - DuPont FilmTec
>    - Toray, which supplied the Taweelah membranes
>    - Hydranautics (Nitto)
>    - LG Chem

yes but LG Chem site would not open and S42 is correct and okay to the last todo-verify
```
*AI: removed LG Chem and the unverified Werber citation; all 48 checklist entries ticked.*

## Part 4: AI log

**33.** *[Uploaded file: `02-critique.md`, a critique of the plan by a second AI model (Muse).]*

*AI: saved it verbatim and answered all 12 points in `03-decisions.md` (4 changed now, 6 already resolved, 2 rejected with measurements).*

**34.**
```text
Put the prompts on there
```
*AI: wrote this file (messages 1–34; later messages were added as they came).*

**35.**
```text
You can find the planning prompt in the pinned separation process conversation find only the parts about the project and put it on there
```
*AI: could not reach that conversation (only this cloud session and an unrelated one were accessible) and asked the student to paste it.*

**36.** *[The student pasted the whole planning conversation from claude.ai: the course's AI-project instructions, the lecture review, the choice of reverse osmosis, and the plan-mode prompt. Its project-related messages are recorded verbatim in [`01-planning-session.md`](01-planning-session.md).]*

*AI: wrote `01-planning-session.md` and flagged that the course requires implementing the plan with at least two different AI models, which had not been done yet; suggested a prompt for the second model.*

## Part 5: the second AI model's implementation

**37.** *[Uploaded files from Muse: `ro_model_COMPARISON_NOTES.md`, `03-decisions-patched.md` and its `ro_model.py` (also uploaded once as an unfinished browser download, `Unconfirmed_12907.crdownload`, which turned out to be the same file). Sent in two parts, after interrupting the AI.]*

*AI: saved the files verbatim, ran both models side by side, found that Muse's model never applies the temperature correction, accepted Muse's molality and wording fixes, and wrote up the comparison (M1–M10).*

**38.** *[The student pasted the conversation with Muse: its critique, its audit of the decisions log and the two messages the student sent it. Recorded in [`03-muse-session.md`](03-muse-session.md).]*

*AI: saved the Muse conversation and answered its three remaining audit points (M11–M13).*

**39.**
```text
okay update the prompts with the new prompts as well
```
*AI: added messages 35–39 to this file.*

**40.**
```text
make sure the website is fully ready besides the video because the website has words on it like awaiting human verification
```
*AI: replaced the out-of-date statuses (“Ongoing”, “Awaiting human check”), rewrote the AI statement to name every model and service used, added “Where the student steered” to §7, and updated the attribution.*
