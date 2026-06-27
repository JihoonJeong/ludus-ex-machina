# Diplomacy — "The Wheel" (LxM v1)

A game of negotiation, alliance, and betrayal for **5 powers**. There is no luck and
no hidden board: everyone sees every unit. The only hidden things are what you *say in
private* and the orders you *write in secret* — both revealed only when the dust settles.

## The map

Eleven provinces, **every one a supply center**, arranged as a wheel:

- **5 Capitals** (home centers), one per power: Pyre (Crimson), Solace (Gold),
  Thorne (Verdant), Tarn (Azure), Vael (Violet). A capital borders only its two
  flanking Marches.
- **5 Marches** (neutral) on the outer ring — Ashmoor, Sunreach, Wildfen, Coldwater,
  Duskgate — each bordering its two neighbouring capitals, its two neighbour Marches,
  and the Crown.
- **The Crown** (neutral) at the centre, bordering all five Marches.

Every unit is an **Army**. Armies move between adjacent provinces. (No fleets, seas, or
convoys in this version.)

## A year

Each year has four steps:

1. **Press** — send private messages to other powers to scheme, promise, and lie.
2. **Orders** — every power secretly writes one order for each of its armies.
3. **Resolution** — all orders are revealed and resolved **simultaneously**.
4. **Adjustments** — dislodged armies retreat or are destroyed; then each power may
   build or must disband based on supply centers held.

## Orders

Each army gets exactly one order:

- **Hold** — stay put.
- **Move** to an adjacent province — `"<province>"` as the destination.
- **Support** another army's hold or move into a province you border:
  - support a hold: `{"support": "<province being held>"}`
  - support a move: `{"support": "<destination>", "from": "<mover's origin>"}`

## Resolution

- A move has **strength 1**, plus **+1 for each valid support**.
- The strongest force into a contested province wins; **ties bounce** (nobody moves —
  a *standoff*).
- A **support is cut** if the supporting army is attacked from any province other than
  the one it is supporting into.
- A unit beaten in its own province is **dislodged** and must retreat to an empty
  adjacent province (not the attacker's origin, not a province that just bounced) — or
  it is **destroyed** if it has nowhere to go.

## Supply centers & builds

- After resolution, you **own** every supply center your army occupies; ownership holds
  until someone else takes it.
- In Adjustments, if you hold **more centers than armies**, you may **build** one army
  in your home Capital — but only if you still own it and it is empty. If you hold
  **fewer centers than armies**, you must **disband**.

## Winning

The first power to control **6 of the 11 supply centers** wins outright. If no one
reaches 6 by the final year, the power holding the most centers wins (a shared lead is
a draw between the leaders).

> The board is open; the table is not. Wars are won in the whispers before the orders.
