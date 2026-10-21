# Full reviewer evidence: access, contents, and SHA-256 verification

**Do not mistake the small public GitHub source ZIP for the full experimental evidence archive.**

The current author-controlled backup, `MAPE_PAPER2_COMPLETE_REVIEWER_EVIDENCE_20261022.tar.zst`, is **417,004,855 bytes** (about 398 MiB compressed) with SHA-256:

`4e683de510c5bb45c5687c2f78b14fe10849ca8023009e638b749127ceae2752`

It contains the current 18-page *Engineering Reports* manuscript and 12-page supplement, original source, frozen experiments, derived tables, and **ten raw-study ZIPs holding 108,727 indexed experimental records** (about 9.03 GiB extracted). It has been verified separately from GitHub. The experimental records were preserved unchanged from the earlier verified release; the 22 October 2026 manuscript files were synchronized into the author backup.

After **authorized receipt** of the archive, verify it from a public-repository checkout:

```bash
python3 00_START_HERE/verify_offline_backup.py --archive /path/to/MAPE_PAPER2_COMPLETE_REVIEWER_EVIDENCE_20261022.tar.zst
tar --zstd -xf MAPE_PAPER2_COMPLETE_REVIEWER_EVIDENCE_20261022.tar.zst
python3 /path/to/public-repo/00_START_HERE/verify_offline_backup.py --root MAPE_PAPER2_COMPLETE_REVIEWER_EVIDENCE_20261022
cd MAPE_PAPER2_COMPLETE_REVIEWER_EVIDENCE_20261022
python3 00_START_HERE/verify_release.py
```

The last command checks the archived file and raw-record SHA-256 digests and selected outcome recalculations. It does not rerun ns-3 or Kubernetes or match every archived bootstrap random draw. See [ten original study ZIP hashes](OFFLINE_RAW_STUDY_SHA256SUMS.txt).

**Sharing status:** This complete archive has **no public GitHub download URL**. It remains with the author; coauthor and third-party rights, a complete metadata/privacy review, and a journal-accepted raw-data transfer route have not been established. Publishing the full raw ZIPs publicly now would be an unverified redistribution. A corresponding author can arrange permission-cleared access through the editorial process.

The historical B3 Stage-A `calibration_aggregated.csv` remains unavailable and cannot be supplied even in the full archive. The full upstream SNOB5G dataset is not redistributed. Public result tables and scripts already allow independent verification of selected findings without packet logs.
