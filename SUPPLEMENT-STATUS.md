# Status of the pilot-era `paper.pdf` — READ BEFORE CITING OR DISTRIBUTING

An earlier version of this audit circulated as an 8 pp USENIX-format
document (SHA-256
`c3307de5647de9588ceb8d13ae2aa373b6951c6f03760f1d8fcf3841e0784192`), the
**preserved pilot-era version**, retained as a historical record in the
project repository. It is **superseded in full** by the PoPETs manuscript
"Verifiability Is a Spectrum: An Outsider's Audit of Google's
Sealed-Hardware Federated Learning Pipeline" — in this artifact, the
bundled `paper.pdf` — which **governs** wherever the two disagree. The
preserved document's content has not been altered; this note is the label
that travels with the artifact so a reader who encounters the pilot-era
version elsewhere can place it.

Correction map — the preserved version's claims that the manuscript
corrects or narrows:

1. **Search/enumeration**: the preserved version reports the endorsement
   entries as not searchable by key. The manuscript executes the
   enumeration via Rekor's index endpoint (§4.4, §5): 509,569 entries
   over 19 reconstructable keys, with three residual trust-required
   dependencies (C3b, C3c, retention).
2. **Rebuild**: the preserved version reports no executed rebuild. The
   manuscript executes the project's CI invocation and reproduces the
   endorsed digest bit-for-bit for the exemplar-era tree (§4.3), scored
   P (single instance; exploratory rescue).
3. **"20 CI builds" reproducibility**: the preserved version reads the 20
   identical-digest provenance records as reproducibility evidence. The
   manuscript scores them as provenance *observation* (§4.1, §5):
   input-sensitivity is not established; the executed check is one
   rebuild of one tree.
4. **Key rotation**: the preserved version treats rotation as
   observable. The manuscript scores rotation *inferred, not announced*
   (row D1; §4.2, §5).
5. **Apple PCC comparison**: the preserved version scores the comparator.
   The manuscript's juxtaposition is document-based and explicitly
   unscored (§6).

Handling rule: any brief or package that includes the pilot-era document
must name it as the superseded pilot-era record and include this label.
Do not overwrite the pilot-era document with manuscript builds — it is a
preserved record, not a manuscript copy.
