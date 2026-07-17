---
title: "Receiving and Inspection — Dock Area"
status: in-review
created: 2025-01-15
updated: 2025-01-17
tags: [observation, receiving, dock]
---

# Receiving and Inspection — Dock Area

## Location / Station

- **Area:** Warehouse — Receiving Zone
- **Station/Cell:** Dock Doors 1-3 (Door 3 is primary for inbound freight)
- **Address/Building:** Building A, Ground Floor, East Side

## Activity

Inbound materials are received at the dock, unloaded from trucks, counted, inspected for damage, and staged for putaway. This is the entry point for all raw materials and purchased components entering the facility.

## Inputs

| Input | Source | Format | Notes |
|---|---|---|---|
| Palletized materials | Suppliers via freight carriers | Physical pallets, shrink-wrapped | Typically 4-12 pallets per delivery |
| Purchase order (PO) | Purchasing department | Printed PO packet, also in SAP | Operator gets paper copy from supervisor each morning |
| Bill of lading (BOL) | Truck driver | Paper document, 3 copies | Driver keeps one, receiving keeps one, office gets one |
| Advance ship notice (ASN) | Supplier via email | PDF attachment | Not all suppliers send these; about 60% compliance |

## Outputs

| Output | Destination | Format | Notes |
|---|---|---|---|
| Inspected pallets | Staging area (yellow-taped floor zone) | Physical pallets with "INSPECTED" sticker | Wait here until forklift moves them to racks |
| Receiving report | Office / SAP | Paper form, manually entered into SAP later | Maria in the office enters these by end of day |
| Discrepancy report | Supervisor → Purchasing | Paper form, pink carbon copy | Used when count doesn't match PO or damage found |
| Rejected materials | Quarantine area (red-taped zone near dock 1) | Physical pallets with "REJECTED" tag | Supplier contacted within 24 hours for pickup/credit |

## People

| Role | Count | Shift/Schedule | Notes |
|---|---|---|---|
| Receiving Operator | 2 | Day shift, 6:00 AM - 2:30 PM | Carlos and Miguel alternate between dock and staging |
| Forklift Driver | 1 (shared) | Day shift | Shared with shipping; receiving gets priority before 10 AM |
| Receiving Supervisor | 1 | Day shift | Tom oversees receiving and shipping; office is 50 ft from dock |

## Timing

- **Frequency:** 3-6 deliveries per day, Monday through Friday
- **Duration:** 20-45 minutes per delivery (unload + count + inspect)
- **Schedule:** Most deliveries arrive between 7:00 AM and 11:00 AM. Afternoon deliveries (1-2 per week) cause delays because the forklift is usually with shipping.
- **Peak/Off-peak:** Monday and Thursday are heaviest (suppliers batch shipments). Friday afternoons are quiet.

## Equipment and Tools

| Equipment | Purpose | Notes |
|---|---|---|
| Handheld barcode scanner (Zebra MC9300) | Scan pallet labels and PO barcodes | 2 scanners; one frequently loses WiFi connection near dock 3 |
| Pallet jack (manual) | Move pallets on dock | Electric pallet jack requested but not yet approved |
| Dock leveler | Bridge gap between truck and dock floor | Door 2 leveler sticks; operators use door 3 when possible |
| Inspection table | Visual inspection of sample items | Metal table, 4x8 ft, near door 3 |
| Scale (floor) | Weigh pallets for weight-based receiving | Calibrated quarterly; last calibration 2024-11-20 |

## Systems

| System | Used For | Notes |
|---|---|---|
| SAP MM (Materials Management) | Look up PO, confirm receipt | Operators don't enter into SAP directly — they fill paper forms |
| Scanner software (custom) | Scan barcodes, display PO info | Runs on the Zebra handhelds; crashes when battery drops below 20% |
| Shared Excel spreadsheet | Track daily receiving volume | Carlos updates this daily; saved on shared network drive |

## Handoffs

- **Comes from:** Supplier/carrier delivers to dock. Purchasing issues PO beforehand.
- **Goes to:** Inspected pallets go to staging area, then forklift driver moves to rack location (putaway). Receiving report goes to office for SAP entry.

## Problems and Workarounds

| Problem | Frequency | Current Workaround | Impact |
|---|---|---|---|
| Scanner loses WiFi near dock 3 | 2-3 times/day | Operator walks to staging area to reconnect, then returns to dock | Adds 5-10 min per occurrence; breaks flow |
| PO packet not ready when truck arrives | 1-2 times/week | Operator calls supervisor; supervisor prints from office | Truck waits 10-15 min; driver sometimes complains |
| No ASN from supplier | ~40% of deliveries | Operator counts everything manually instead of verifying against ASN | Adds 10-15 min per delivery; higher error rate on counts |
| Pallet labels unreadable (damaged/smudged) | 1-2 per week | Operator manually types item number from packing slip | Slow, error-prone; wrong item number entered twice last month |
| SAP data entry delayed | Daily | Maria batches all entries at end of day | Inventory not accurate until next morning; causes issues for production planning |

## Photos / Diagrams

- Photo 1: Dock door 3 with typical delivery staged (see `photos/dock-3-overview.jpg`)
- Photo 2: Inspection table setup with sample items laid out (see `photos/inspection-table.jpg`)
- Photo 3: "INSPECTED" and "REJECTED" sticker examples (see `photos/stickers.jpg`)

## Raw Notes

Visited 2025-01-15, 7:30 AM - 10:00 AM. Observed two deliveries. Carlos was primary operator.

First delivery (steel fasteners, 6 pallets) went smoothly — 25 min total. Second delivery (electrical components, 8 pallets) had two pallets with damaged shrink wrap. Carlos pulled sample items from each damaged pallet for inspection. Found one box with water damage; rejected that pallet, remaining 7 accepted.

Carlos mentioned that the biggest pain point is the WiFi dropout. He's submitted three IT tickets in the past year. IT says they need to install an access point closer to the dock but it hasn't been prioritized.

Tom (supervisor) mentioned they're supposed to do 100% count verification for new suppliers and 10% spot-check for established suppliers, but "in practice, if we're backed up, we just check the pallet count and move on." This was observed — the second delivery was spot-checked only.

## Open Questions

1. What is the error rate on manual item number entry when pallet labels are unreadable? Carlos mentioned "twice last month" but is there a log?
2. What is the actual vs. stated inspection sampling policy? Tom said 10% spot-check for established suppliers but practice seems looser.
3. How does the delayed SAP entry affect production planning? Need to talk to the production scheduler.
4. Is the shared Excel spreadsheet the only way receiving volume is tracked, or does SAP have a report?
5. What happens to rejected pallets if the supplier doesn't arrange pickup within 24 hours? How long do they sit in quarantine?
