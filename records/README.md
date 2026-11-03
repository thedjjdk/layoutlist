# Website record submissions

Each submitted record is saved at `<level-slug>/<submission-id>.json`. Its contents
match one object in an official level file's `records` array, for example:

```json
{
  "user": "ExamplePlayer",
  "link": "https://youtu.be/VIDEO_ID",
  "percent": 100,
  "hz": 240,
  "mobile": false
}
```

This is an example only. No sample submissions are stored in this folder.

`index.json` tracks submission IDs, associated levels, public notes, pending /
accepted / rejected status, decision revisions, staff attribution and timestamps.
`approved.json` is the compact website feed of accepted records only. Submission
files remain intact after approval or rejection. A pending or rejected record is
never counted merely because its file exists.

The record service updates the submission file, index and approved feed together
in a single Git commit. It refuses stale decisions and never force-pushes over
other repository edits. Staff codes and GitHub credentials are server secrets;
they never belong in this folder or in the public index.html.

The Pending Approval page is the review interface. It lists proof links and opens
an individual staff-code prompt for each approve/reject action. Rejection needs a
public reason. The website's official upstream data repository is unchanged.
