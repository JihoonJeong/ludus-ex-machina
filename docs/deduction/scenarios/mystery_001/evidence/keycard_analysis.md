# Keycard Forensic Analysis

## Card KC-0447 — Technical Report

The IT Security team analyzed the encryption signature of card KC-0447 as recorded by the access control system.

### Findings

1. **Card format:** Standard HID iCLASS SE, compatible with NovaTech's access system.

2. **Encryption key:** The card uses NovaTech's facility master key, confirming it was programmed using NovaTech's own card programming equipment (or a copy of the master key).

3. **Card serial origin:** The internal serial number of KC-0447 shares a manufacturing batch prefix with cards KC-0100 through KC-0150 — the batch issued to NovaTech employees between January and June 2025.

4. **Clone signature:** The card's sector layout is identical to card **KC-0112**, which was previously assigned to **David Kwon (former Senior Engineer)**. KC-0112 was deactivated in the access system on January 15, 2026 when Mr. Kwon was terminated. However, KC-0447 appears to be a **physical clone** of KC-0112 with a different card number written to the ID sector.

5. **Programming timestamp:** The card's internal programming timestamp reads **February 28, 2026** — approximately 6 weeks after Mr. Kwon's termination.

### Conclusion

Card KC-0447 is a clone of David Kwon's former access card KC-0112. It was created after his termination using equipment capable of reading and writing HID iCLASS SE cards. During his employment, Mr. Kwon had authorized access to the card programming station in the IT room as part of his facilities management responsibilities.
