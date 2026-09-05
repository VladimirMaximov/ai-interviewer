# Candidate and Reviewer API Contract

| Operation | Authorization | Result |
|---|---|---|
| Resolve invitation | Invitation secret | Safe session metadata; invalid tokens reveal nothing |
| Record consent | Valid active invitation | Starts the session |
| Request upload grant | Valid active invitation + current question | Short-lived grant scoped to one unsent response |
| Confirm upload | Valid active invitation | Saves/replaces an unsent response and starts transcription |
| Start continuous recording / request fragment grant / confirm fragment | Valid active invitation + consent | Private recording manifest and ordered fragment upload grants |
| Save answer boundary | Valid active invitation + active recording | Stores answer start/end offsets; transcription continues in background once covered by confirmed media |
| List ready follow-ups | Valid active invitation | Candidate-safe optional clarifications already queued for this session |
| Resume | Valid active invitation | Saved progress and current question |
| Submit | Valid active invitation | Only succeeds when required answers are confirmed |
| View interview | Assigned recruiter/hiring manager | Completed answers, status, and traceable evidence |

Errors are user-safe: invalid, revoked, expired, or submitted links do not disclose candidate or
interview data. Reviewer authorization is enforced for every read and audio access request.
