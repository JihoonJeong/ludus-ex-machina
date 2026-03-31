# Anonymous Whistleblower Email

**Source:** PayBridge Inc. Board of Directors, forwarded to Seoul Metropolitan Police
**Received:** February 28, 2026

## Original Email

```
From: paybridge.truth2026@protonmail.com
To: board@paybridge.co.kr
Date: February 28, 2026, 11:47 PM
Subject: [URGENT] Financial irregularities — CFO involvement

Dear Board Members,

I am writing anonymously because I fear retaliation. I have evidence that
CFO Choi Seoyeon has been siphoning company funds through fake vendor
accounts. She has been approving payments to companies that don't exist.

Check the payment approval records — her electronic signature is on every
fraudulent transfer. She has been doing this since December.

I urge you to investigate immediately before more money disappears.

A concerned employee
```

## Police Digital Forensics Analysis

### Email Service
- Sent via ProtonMail (encrypted email service, Switzerland-based)
- ProtonMail does not retain sender IP addresses by default

### However:
- The email was composed and sent through ProtonMail's **web interface** (not the app)
- PayBridge's corporate email server logs show the inbound email's routing headers
- The ProtonMail web session metadata, obtained through mutual legal assistance treaty (MLAT) request, included a **browser fingerprint hash**

### Browser Fingerprint Correlation

The browser fingerprint hash from the ProtonMail session was compared against fingerprints collected from PayBridge's internal web services (which track browser fingerprints for security purposes):

| Source | Browser Fingerprint Hash | Match |
|--------|------------------------|-------|
| Whistleblower email session | a3f7c2d1e8b... | — |
| Park Jaemin (CTO) — home network sessions | a3f7c2d1e8b... | **MATCH** |
| Choi Seoyeon (CFO) — all sessions | 9b2e5f8a1c4... | No match |
| Lee Haneul (Marketing) — all sessions | 6d4a8c3f7e2... | No match |
| Kang Dohyun (Accounting) — all sessions | f1c9d5b2a8e... | No match |

### Analysis

The anonymous email was sent from a browser environment matching **Park Jaemin's home network browser fingerprint**. The email specifically directs attention to CFO Choi Seoyeon and her payment approvals — which are legitimate approvals made as part of normal business process (see: financial_approvals.md).

**Assessment: The anonymous tip appears to be a deliberate attempt to misdirect the investigation toward the CFO by someone using Park Jaemin's home browser.**
