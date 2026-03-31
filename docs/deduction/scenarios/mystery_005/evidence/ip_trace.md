# IP and Device Trace — Shell Company Registrations

**Source:** Seoul Metropolitan Police Cyber Investigation Unit
**Cooperation:** Korea Internet & Security Agency (KISA), Corporate registration service provider

## Investigation Summary

Police traced the digital footprint of the three shell company registrations (Bluewave Solutions, Nextform Digital, Greenfield Data Corp.) through the online corporate registration service used to create them.

## Registration Access Records

| Company | Registration Date | IP Address | Connection Type |
|---------|------------------|------------|-----------------|
| Bluewave Solutions | Oct 12, 2025 | 211.234.XX.XX | PayBridge Corp. VPN |
| Nextform Digital | Oct 28, 2025 | 211.234.XX.XX | PayBridge Corp. VPN |
| Greenfield Data Corp. | Nov 5, 2025 | 211.234.XX.XX | PayBridge Corp. VPN |

**All three registrations originated from the same IP address — PayBridge's corporate VPN endpoint.**

## VPN Session Analysis

PayBridge's VPN system logs device identifiers (MAC addresses) for each authenticated session:

| Date | VPN User | Device MAC Address | Session Duration |
|------|----------|--------------------|-----------------|
| Oct 12, 2025 | park.jaemin | **7C:D1:C3:8A:2F:E9** | 20:15 – 21:40 |
| Oct 28, 2025 | park.jaemin | **7C:D1:C3:8A:2F:E9** | 21:30 – 22:15 |
| Nov 5, 2025 | park.jaemin | **7C:D1:C3:8A:2F:E9** | 22:00 – 22:50 |

## Device Identification

MAC address **7C:D1:C3:8A:2F:E9** was identified through PayBridge IT asset records:

| Field | Value |
|-------|-------|
| Device | MacBook Pro 16" (2024) |
| Serial | C02GR3XXXXX |
| Assigned to | **Park Jaemin (CTO)** |
| Purchase date | March 2024 |
| Status | Personal device (BYOD), registered with PayBridge IT |

## Key Finding

The shell companies were registered from **Park Jaemin's personal MacBook** connected through **PayBridge's corporate VPN**, using **Park Jaemin's VPN credentials**.

This device is distinct from Park Jaemin's office workstation (a desktop Mac Studio, MAC address 3C:22:FB:XX:XX:XX), which is the device logged in the PFMP maintenance records.

## Technical Note

- MAC addresses can theoretically be spoofed, but the VPN system also recorded the device's hardware serial number via the MDM (Mobile Device Management) agent installed on all BYOD devices.
- The MDM serial number matches the MacBook Pro assigned to Park Jaemin.
- **The shell company registrations were made from a different device than the one used for PFMP maintenance — undermining the claim that vendor module access was incidental to system maintenance.**
