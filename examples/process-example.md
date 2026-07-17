---
title: "Incoming Material Inspection Process"
status: in-review
created: 2025-01-18
updated: 2025-01-20
tags: [process, receiving, inspection]
---

# Incoming Material Inspection Process

## Process Overview

- **Purpose:** Verify that incoming materials match the purchase order in quantity, identity, and condition before accepting them into inventory.
- **Trigger:** A delivery truck arrives at the dock and the driver checks in with the receiving operator.
- **End condition:** All pallets from the delivery are either accepted (moved to staging) or rejected (moved to quarantine), and the receiving report is completed.
- **Frequency:** 3-6 times per day, Monday through Friday.
- **Typical duration:** 20-45 minutes per delivery, depending on pallet count and whether exceptions occur.

## Roles Involved

| Role | Responsibility in This Process |
|---|---|
| Receiving Operator | Unloads, counts, inspects, and documents incoming materials |
| Forklift Driver | Moves accepted pallets from staging to rack locations |
| Receiving Supervisor | Resolves discrepancies, authorizes rejections, manages exceptions |
| Office Admin (Maria) | Enters receiving reports into SAP by end of day |

## Inputs

| Input | Source | Notes |
|---|---|---|
| Physical pallets | Supplier via freight carrier | 4-12 pallets typical |
| Purchase order (PO) packet | Supervisor (printed from SAP) | Paper copy, prepared morning of delivery |
| Bill of lading (BOL) | Truck driver | 3 copies: driver, receiving, office |
| Advance ship notice (ASN) | Supplier via email (when available) | ~60% of suppliers send ASNs |

## Outputs

| Output | Destination | Notes |
|---|---|---|
| Accepted pallets with "INSPECTED" sticker | Staging area → rack locations | Forklift driver handles putaway |
| Rejected pallets with "REJECTED" tag | Quarantine area near dock 1 | Supplier contacted within 24 hours |
| Completed receiving report | Office → SAP entry | Paper form, entered by Maria at end of day |
| Discrepancy report (when applicable) | Supervisor → Purchasing | Pink carbon copy form |

## Process Steps

### Main Flow

1. Truck arrives at dock. Driver checks in with receiving operator and presents bill of lading.
2. Operator verifies a purchase order exists for the delivery. Operator matches PO number on BOL to the printed PO packet.
   - **If PO packet is available:** Continue to step 3.
   - **If PO packet is missing:** Go to Exception A.
3. Operator directs truck to open dock door (door 3 preferred; door 1 or 2 if door 3 occupied).
4. Operator unloads pallets onto dock using manual pallet jack. Pallets are lined up in receiving order.
5. Operator scans each pallet barcode label with handheld scanner.
   - **If barcode scans successfully:** Scanner displays item number and expected quantity. Continue to step 6.
   - **If barcode is unreadable:** Go to Exception B.
6. Operator counts items on the pallet and compares to PO expected quantity.
   - **For new suppliers:** 100% count verification required.
   - **For established suppliers:** 10% spot-check (count every 10th pallet fully, verify pallet count for the rest).
7. Operator checks count result.
   - **If count matches PO (within tolerance of +/- 2%):** Continue to step 8.
   - **If count does not match:** Go to Exception C.
8. Operator performs visual inspection for damage.
   - **If no damage found:** Continue to step 9.
   - **If damage found:** Go to Exception D.
9. Operator applies "INSPECTED" sticker to each accepted pallet.
10. Operator moves accepted pallets to staging area (yellow-taped floor zone).
11. Operator completes receiving report form: date, PO number, item numbers, quantities received, any notes.
12. Operator signs BOL, gives driver copy, and places receiving copy in the office inbox tray.
13. Forklift driver moves pallets from staging to assigned rack locations (putaway).

### Exception A: PO Packet Missing

A1. Operator calls supervisor (Tom) to report missing PO packet.
A2. Supervisor looks up PO in SAP and prints a copy from the office (takes 10-15 minutes).
A3. Truck waits at dock during this time.
A4. Once PO packet is delivered to the dock, return to main flow at step 3.

### Exception B: Unreadable Barcode

B1. Operator locates packing slip on the pallet (usually in an envelope attached to shrink wrap).
B2. Operator manually types item number from packing slip into scanner.
B3. Scanner displays expected quantity. Return to main flow at step 6.
B4. If no packing slip is found, operator contacts supervisor to identify item from PO description.

### Exception C: Quantity Mismatch

C1. Operator recounts the pallet to confirm the discrepancy.
C2. If recount still shows mismatch, operator fills out discrepancy report (pink form).
C3. Operator notes actual quantity vs. expected quantity and signs the form.
C4. Supervisor reviews and countersigns within 1 hour.
C5. Materials are accepted at the actual count. Supervisor notifies purchasing of the short/over shipment.
C6. Return to main flow at step 8 (proceed with visual inspection).

### Exception D: Damage Found

D1. Operator pulls sample items from damaged pallet(s) and places on inspection table.
D2. Operator assesses whether damage affects usability.
   - **If minor cosmetic damage (scuffed packaging, dented box but contents intact):** Operator notes damage on receiving report. Accept the pallet. Return to main flow at step 9.
   - **If functional damage (crushed items, water damage, broken seals):** Continue to D3.
D3. Operator tags pallet with "REJECTED" tag and moves to quarantine area (red-taped zone near dock 1).
D4. Operator fills out discrepancy report noting type and extent of damage.
D5. Supervisor contacts supplier within 24 hours to arrange return or credit.
D6. For partially damaged pallets: operator separates good items from damaged items. Good items continue through main flow. Damaged items go to quarantine.

## Flow Diagram

```
Truck Arrives → Check BOL → Match PO → Unload → Scan → Count → Inspect → Accept → Stage → Putaway
                  ↓ no PO        ↓ bad scan   ↓ mismatch  ↓ damage
              [Exc. A]        [Exc. B]      [Exc. C]    [Exc. D]
              Get PO from      Manual        Recount →    Assess →
              supervisor       entry from    Discrepancy  Accept or
              → resume         packing slip  report →     Reject →
                               → resume      accept at    Quarantine
                                             actual count
```

## Connected Processes

- **Upstream:** Purchasing creates PO in SAP. Supplier ships against PO. Some suppliers send ASN via email.
- **Downstream:** Putaway process (forklift driver moves pallets to rack locations). SAP inventory update (Maria enters receiving reports). Production planning uses inventory data for scheduling.
- **Related:** Quality hold process (for materials that need lab testing before release). Supplier scorecard process (purchasing tracks delivery accuracy quarterly).

## Systems and Tools

| Step | System/Tool | How It's Used |
|---|---|---|
| 2 | Paper PO packet | Operator matches BOL to printed PO |
| 5 | Zebra MC9300 scanner + custom software | Scan barcode, display item info |
| 5 | WiFi network | Scanner connects to system via WiFi (unreliable near dock 3) |
| 11 | Paper receiving report form | Operator fills in by hand |
| 13 | SAP MM | Maria enters receiving report data at end of day |
| — | Shared Excel spreadsheet | Carlos tracks daily receiving volume (informal) |

## Known Issues

| Issue | Impact | Current Workaround |
|---|---|---|
| WiFi drops near dock 3 | Scanner disconnects 2-3 times/day; operator walks to staging area to reconnect. Adds 5-10 min per event. | IT ticket open (3 submitted, none resolved). Operators try to stay near staging area when possible. |
| SAP entry delayed until end of day | Inventory records not current until next morning. Production planning may schedule against inaccurate stock levels. | Production scheduler calls Maria to ask "did we get the XYZ delivery?" informally. |
| Inspection sampling not enforced | Spot-check policy (10% for established suppliers) is bypassed when backed up. All pallet count only. | No formal workaround. Risk accepted informally. |
| Manual pallet jack on dock | Slower unloading, operator fatigue by end of shift. Electric pallet jack requested but not approved. | Operators rotate unloading duties when possible. |

## Open Questions

1. What is the tolerance policy for quantity mismatches? The +/- 2% tolerance is verbal from Tom — is it documented anywhere in the quality system?
2. How are rejected materials tracked after they go to quarantine? Is there a log or just the pink discrepancy form?
3. What happens if Maria is absent? Does SAP entry wait until she returns, or does someone cover?
4. Are there materials that require lab testing or quality hold before they can be released to production? If so, how does that interact with this process?
5. What is the actual dock-to-stock lead time when all steps are considered (receiving + SAP entry + putaway)? Current estimate is same-day receiving but next-day SAP visibility.
