# Daily refresh (run by the scheduled task)

1. Read the live NolCom artifact page (Artifact tool, action "read", url https://claude.ai/artifact/SDmBUbnmgEH2ukWGz52yT7) and save the full HTML as /tmp/nolcom/page.html.
2. Dump every database collection of that artifact with ArtifactData "list" (limit 1000, follow next_cursor) using out_dir /tmp/nolcom/dbdump.
   Collections: books dossiers games gidx injrep kp lineups logs notes opp previews query recaps reports scout slate teams threads toplines trends updates
3. python3 tools/netlify_build.py --password "$PASSWORD" --salt "$(cat tools/salt.txt)" --dump /tmp/nolcom/dbdump --page /tmp/nolcom/page.html --out /tmp/nolcom/site
4. Replace everything in the repo except .git, tools/ and README.md with the contents of /tmp/nolcom/site, commit, push to main. Netlify deploys automatically.
The password is never stored in this repository.
