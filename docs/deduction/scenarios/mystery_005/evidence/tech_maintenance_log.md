# Technical Maintenance Log — PayBridge Inc.

**Source:** PayBridge IT Department, internal ticketing system (Jira)
**Extracted by:** Seoul Metropolitan Police Digital Forensics Unit

## Scheduled Maintenance Windows

PayBridge IT policy requires quarterly server maintenance. The CTO (Park Jaemin) personally oversees critical financial system updates due to the sensitive nature of payment processing infrastructure.

### Q4 2025 – Q1 2026 Maintenance Records

| Ticket ID | Date | Time | Engineer | System | Description | Status |
|-----------|------|------|----------|--------|-------------|--------|
| MAINT-247 | Oct 10, 2025 | 22:00-00:30 | Park Jaemin | PFMP | "Q4 security patch + vendor module update" | Completed |
| MAINT-248 | Oct 15, 2025 | 23:00-01:00 | Kim Soojin (DevOps) | Payment Gateway | "SSL certificate renewal" | Completed |
| MAINT-251 | Oct 26, 2025 | 22:00-00:00 | Park Jaemin | PFMP | "Database index optimization + vendor table restructure" | Completed |
| MAINT-255 | Nov 3, 2025 | 23:00-01:00 | Park Jaemin | PFMP | "API endpoint migration + vendor module hotfix" | Completed |
| MAINT-260 | Dec 16, 2025 | 21:00-23:30 | Park Jaemin | PFMP | "Year-end compliance update + invoice processing patch" | Completed |
| MAINT-268 | Jan 12, 2026 | 22:00-00:00 | Kim Soojin (DevOps) | Payment Gateway | "PCI-DSS compliance scan" | Completed |
| MAINT-271 | Jan 20, 2026 | 22:00-00:00 | Park Jaemin | PFMP | "Q1 security patch + billing module update" | Completed |
| MAINT-275 | Feb 12, 2026 | 22:30-01:00 | Park Jaemin | PFMP | "Data retention policy update + invoice archival" | Completed |

## CTO Statement (Park Jaemin)

When confronted with the server access logs showing his employee ID accessing the vendor registration module during the flagged timeframes:

> "Those timestamps align with scheduled maintenance windows. I was performing system updates — I have Jira tickets for every session. The vendor module is part of the PFMP system. When I run security patches or database optimizations, the system logs all module access, including vendor registration. The logs don't distinguish between 'viewing vendor data during a system update' and 'actively creating a vendor.' I was maintaining the system, not creating shell companies."

## IT Team Corroboration

- DevOps engineer Kim Soojin confirmed: "Mr. Park handles all PFMP maintenance personally. He's the original architect of the system. Nobody else on the team has the depth of knowledge to maintain it safely."
- Jira ticket creation timestamps match: tickets were created 1-3 days before each maintenance window, consistent with planned maintenance.
- **However:** Jira tickets are created by the CTO himself. No independent verification of the actual maintenance activities performed during these windows exists.
