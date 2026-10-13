# Daily refresh (run by the scheduled task)

1. Read the live NolCom artifact page (Artifact tool, action "read", URL given in the task prompt) and save the full HTML as /tmp/nolcom/page.html.
2. Dump every database collection of that artifact with ArtifactData "list" (limit 1000, follow next_cursor) using out_dir /tmp/nolcom/dbdump.
   Collections: books dossiers games gidx injrep kp lineups logs notes opp previews query recaps reports scout slate teams threads toplines trends updates
3. python3 tools/netlify_build.py --public --dump /tmp/nolcom/dbdump --page /tmp/nolcom/page.html --out /tmp/nolcom/site
4. Replace everything in the repo except .git, tools/ and README.md with the contents of /tmp/nolcom/site, commit, push to main. Netlify deploys automatically.
The site is public (no password) since Oct 13, 2026: the build ships its key in index.html. tools/salt.txt is only used by the old --password mode.
