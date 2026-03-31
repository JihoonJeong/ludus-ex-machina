# Server Access Log — PayBridge Financial Systems

**Extracted by:** Seoul Metropolitan Police Digital Forensics Unit
**Date range:** October 2025 – February 2026
**System:** PayBridge Internal Financial Management Platform (PFMP)

## Relevant Access Records

The following log entries show access to administrative functions related to vendor registration and payment processing:

### Vendor Registration Module (requires admin privileges)

| Date | Time | User ID | Action | Details |
|------|------|---------|--------|---------|
| Oct 10, 2025 | 23:14 | **EMP-CTO-102** | Vendor created | "Bluewave Solutions Ltd." |
| Oct 26, 2025 | 22:47 | **EMP-CTO-102** | Vendor created | "Nextform Digital Inc." |
| Nov 3, 2025 | 23:31 | **EMP-CTO-102** | Vendor created | "Greenfield Data Corp." |
| Dec 16, 2025 | 21:58 | **EMP-CTO-102** | Invoice uploaded | BW-INV-001, ₩380M |
| Jan 20, 2026 | 22:22 | **EMP-CTO-102** | Invoice uploaded | NF-INV-001, ₩450M |
| Feb 12, 2026 | 23:05 | **EMP-CTO-102** | Invoice uploaded | GD-INV-001, ₩370M |

### Employee ID Cross-Reference

| Employee ID | Name | Title |
|-------------|------|-------|
| EMP-CEO-101 | Kim Taewon | CEO |
| **EMP-CTO-102** | **Park Jaemin** | **CTO** |
| EMP-CFO-103 | Choi Seoyeon | CFO |
| EMP-MKT-104 | Lee Haneul | Marketing Director |

## Access Control Notes

- The PFMP vendor registration module requires Level 3 (admin) privileges.
- Three accounts hold Level 3 access: CEO (EMP-CEO-101), CTO (EMP-CTO-102), and CFO (EMP-CFO-103).
- All vendor creation and invoice upload actions for the three shell companies were performed from **EMP-CTO-102 (Park Jaemin, CTO)**.
- All actions occurred between 9 PM and midnight — outside normal business hours.

## System Integrity Check

No evidence of credential theft, session hijacking, or unauthorized privilege escalation was found in system security logs. The EMP-CTO-102 sessions were authenticated using the account holder's registered device fingerprint.
