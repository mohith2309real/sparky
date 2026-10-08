# Sparky 3.0 — roadmap

Sparky 3.0 is the biggest update yet: a new look for everything, signed releases with
real over-the-air updates, and 230 new features across the language, the stage, the
editor, learning, projects and more.

Status: `[x]` built and tested · `[ ]` not built yet · *(later: reason)* when something
can't be done honestly in 3.0.

Each feature has a number so it can be talked about ("feature 64"). The build plan at the
bottom says which build each one lands in.

---

## The redesign — "Spark 3"

**One look for everything Sparky:** the app, the website, the downloads page, the docs,
the lessons, the installers and the app icon all share the same design system.

- **Palette.** Ink `#141413` and cream `#faf9f5` stay as the base. Coral `#d97757` stays
  Sparky's color. New supporting colors are tuned for both themes: sky `#6a9bcc`,
  sage `#8fa377`, sun `#e8b44a`, grape `#9b7fd1`. Every UI color is a named token, so
  themes are just token sets.
- **Type.** Bricolage Grotesque for headings, Figtree for the interface, JetBrains Mono
  for code. These are the website's fonts, bundled inside the app so it looks the same on
  Mac, Windows and Linux. All three are under the SIL Open Font License.
- **Shape.** Rounded cards (radius 10 / 14 / 20), a 4-px spacing grid, soft 1-px hairlines
  instead of heavy borders, and pill buttons for primary actions.
- **Icons.** A custom line-icon set drawn for Sparky, replacing the emoji icons in the UI.
  The mascot stays. Emoji stay in kids' content, where they're fun.
- **Motion.** Short, calm animations: panels slide, buttons press, toasts fade. All of it
  turns off with Reduce Motion.
- **Layout.** A Home screen to start from, a top bar built around Run / Stop / Step, a
  stage card with its own toolbar, a console that shows each kind of message differently,
  and a Settings window with a sidebar instead of tabs.
- **Two modes.** Kid mode keeps the screen simple. Pro mode is the full IDE.

---

## Features

### A. Updates and signing (1–18)

- [ ] 1. **Release signing key.** Sparky gets its own Ed25519 signing key. The private half stays on Mohith's Mac and is never uploaded.
- [ ] 2. **Signed downloads.** Every release ships `SHA256SUMS.txt` plus a signature file, and the public key is published on the website.
- [ ] 3. **Signed update manifests.** `stable.json` and `beta.json` on sparky-code.web.app list the newest version, its files and their hashes, signed with the release key.
- [ ] 4. **Automatic update checks.** Quietly at launch, then every 6 hours while Sparky is open.
- [ ] 5. **Background downloads.** Updates download while you keep coding, with progress in the status bar.
- [ ] 6. **"Restart to update" bar,** like Windows and VS Code, with Later and What's new buttons.
- [ ] 7. **Small code-pack updates.** Most updates are a few MB, because Python and Qt don't need to download again.
- [ ] 8. **Full updates when needed.** When the runtime changes, the Mac app swaps itself, Windows runs the new installer silently, Linux replaces its folder, and Sparky relaunches.
- [ ] 9. **Double-checked updates.** The manifest must carry a valid Ed25519 signature, and every file must match its SHA-256, or nothing gets installed.
- [ ] 10. **Automatic rollback.** If a new version can't start, Sparky goes back to the last version that worked and tells you.
- [ ] 11. **Update channels:** Stable and Beta.
- [ ] 12. **Settings → Updates:** current version, last check, Check now, auto-download on/off, channel, Skip this version.
- [ ] 13. **What's new window** after an update, with the release notes.
- [ ] 14. **Update history:** which versions were installed and when.
- [ ] 15. **Offline-friendly.** No errors or nagging without internet.
- [ ] 16. **Proper version info** in macOS (Get Info) and in the Windows installer and app list.
- [ ] 17. **`sparky selfcheck` covers updates:** it verifies the signature code and the update folder.
- [ ] 18. **Signed news and featured-projects feeds** for the Home screen.

### B. The new look (19–42)

- [ ] 19. **Spark 3 design tokens** for color, spacing, radius and type, shared by the app, website and docs.
- [ ] 20. **Bundled fonts:** Bricolage Grotesque, Figtree and JetBrains Mono on every OS.
- [ ] 21. **Custom line icons** replace the emoji in the toolbar, activity bar and menus.
- [ ] 22. **Home screen:** recent projects with thumbnails, continue learning, templates, examples, news.
- [ ] 23. **New top bar:** big Run / Stop / Step buttons, project name, and a turtle-to-rabbit speed slider.
- [ ] 24. **New activity bar** with icon buttons, tooltips and badges.
- [ ] 25. **Stage card:** a rounded stage with its own toolbar (fullscreen, grid, snapshot, clear).
- [ ] 26. **Console 2.0:** says, questions, answers, errors and info each get their own color and icon, plus Copy and Clear.
- [ ] 27. **Status bar 2.0:** run state, cursor, language, update pill, "by Mohith".
- [ ] 28. **Settings window redesign:** sections in a sidebar (General, Editor, Stage, Sounds, Languages, AI, Updates, Accessibility, Classroom).
- [ ] 29. **Learn window redesign:** a map of worlds and lessons with your stars.
- [ ] 30. **Redesigned dialogs:** Welcome, About, Community, Make an App, Extensions.
- [ ] 31. **Four built-in themes:** Daylight, Midnight, Candy and High Contrast (VS Code themes still work).
- [ ] 32. **Motion:** short animations for panels, buttons and toasts, respecting Reduce Motion.
- [ ] 33. **Toasts** replace pop-up boxes for small messages like "Saved".
- [ ] 34. **Friendly empty states** with the mascot, instead of blank panels.
- [ ] 35. **Sparky mascot redrawn** in vector, with moods: happy, thinking, oops and wow.
- [ ] 36. **New app icon** on Mac, Windows and Linux.
- [ ] 37. **Kid mode and Pro mode:** Kid mode hides advanced panels, Pro mode shows everything.
- [ ] 38. **UI scale** from 90% to 150%.
- [ ] 39. **Native macOS menu bar** (File, Edit, View, Run, Learn, Help) and the same menus on Windows and Linux.
- [ ] 40. **New website design** for sparky-code.web.app.
- [ ] 41. **New downloads page** with OS detection, checksums and signature info.
- [ ] 42. **New brand board, DMG window art and installer branding.**

### C. The language (43–82)

- [ ] 43. **`else if`** chains.
- [ ] 44. **`repeat while`** loops.
- [ ] 45. **`wait until`** a condition is true.
- [ ] 46. **Text templates:** `say "Hi {name}!"`.
- [ ] 47. **`ask number`**, which keeps asking until it gets a number.
- [ ] 48. **Choice questions:** `ask "Pick one" choices ["cat", "dog"] into pet` shows buttons.
- [ ] 49. **Records:** `set pet to {name: "Rex", age: 3}`, `say name of pet`, `set age of pet to 4`.
- [ ] 50. **`mod`** (remainder): `7 mod 3`.
- [ ] 51. **More maths:** `round(x, 2)`, `pi`, `clamp`, `log`, `angle`, `distance`.
- [ ] 52. **More text tools:** `replace`, `begins`, `ends`, `find`, `words`, `letters`, `capital`.
- [ ] 53. **More list tools:** `insert X at N in L`, `index`, `slice`, `range`, `shuffle`, `unique`, `count`.
- [ ] 54. **Counting from the end:** `item -1 of L` is the last item.
- [ ] 55. **`timer`** and `reset timer`.
- [ ] 56. **Date and time:** `hour`, `minute`, `second`, `today`, `weekday`.
- [ ] 57. **`use "shapes.spark"`** shares commands between files.
- [ ] 58. **`try … oops … end`** catches problems without stopping the program.
- [ ] 59. **`say … for 2 seconds`** and **`think "…"`** (a thought bubble).
- [ ] 60. **Key events:** `when key "space" pressed … end`.
- [ ] 61. **Click events:** `when clicked` (a sprite) and `when stage clicked`.
- [ ] 62. **Messages:** `broadcast "go"` and `when message "go"`.
- [ ] 63. **Sensing:** `key "left" down`, `mouse x`, `mouse y`, `mouse down`.
- [ ] 64. **`next frame`** for smooth 60-fps games.
- [ ] 65. **Many sprites:** `make sprite rocket with costume "🚀"`.
- [ ] 66. **`tell rocket … end`** gives commands to one sprite.
- [ ] 67. **Costumes:** emoji or shape costumes, `costume "🐱"`, `next costume`.
- [ ] 68. **Looks:** `ghost 50` (see-through), `layer front` / `layer back`.
- [ ] 69. **Touching:** `touching rocket`, `touching edge`, `distance to rocket`.
- [ ] 70. **`bounce if on edge`.**
- [ ] 71. **`glide to 100 50 in 2 seconds`.**
- [ ] 72. **Shapes:** `circle 50`, `rectangle 80 by 40`, `polygon 6 sides 40`, `star 5 points 40`, `dot 10`, `arc 90 radius 50`.
- [ ] 73. **Filled shapes:** `fill color "yellow"` and `no fill`.
- [ ] 74. **Pen styles:** dashed, dotted, `pen opacity 50`, and a rainbow pen.
- [ ] 75. **Any color:** `"#ff8800"`, `rgb(255, 136, 0)`, `random color`.
- [ ] 76. **Text styles:** `write "Hi" size 30 bold`.
- [ ] 77. **Backdrops:** space, ocean, grass, sunset, night, grid, or an image file.
- [ ] 78. **Memory between runs:** `save score as "best"` and `load "best" into best`.
- [ ] 79. **`speak "Hello"`** uses the computer's voice.
- [ ] 80. **Better errors:** "you wrote / try this" examples for the 30 most common mistakes.
- [ ] 81. **Names in any alphabet:** variables and commands can use Hindi, Telugu and other scripts.
- [ ] 82. **Friendly numbers:** `0.1 + 0.2` says `0.3`, and big numbers stay readable.

### D. Stage, sprites and graphics (83–100)

- [ ] 83. **Resizable stage** that stays crisp at any size (the coordinates stay 480 × 360).
- [ ] 84. **Fullscreen presentation mode.**
- [ ] 85. **Grid and axes overlay.**
- [ ] 86. **Live mouse x / y readout.**
- [ ] 87. **Save the stage as PNG** at 1×, 2× or 4×.
- [ ] 88. **Save the drawing as SVG** (vector).
- [ ] 89. **Copy the stage** to the clipboard.
- [ ] 90. **Record the stage as an animated GIF.**
- [ ] 91. **Pause and resume** a running program.
- [ ] 92. **Turbo mode** (draw instantly).
- [ ] 93. **Faster drawing** with cached layers, for drawings with 100,000+ lines.
- [ ] 94. **Costume picker** with 40 built-in emoji costumes.
- [ ] 95. **Mascot moods on the stage:** happy when done, "oops" on errors.
- [ ] 96. **Confetti** when you finish a challenge.
- [ ] 97. **Stage color** follows the theme, or pick your own.
- [ ] 98. **Sprites panel:** every sprite with its x, y, size and costume.
- [ ] 99. **Click the stage to copy `x y`** for `goto`.
- [ ] 100. **Direction arrow** on the sprite (toggle).

### E. Editor (101–124)

- [ ] 101. **Auto `end`:** press Enter after `repeat`, `if`, `teach` or `for` and the `end` appears.
- [ ] 102. **Matching blocks:** put the cursor on `end` and its `repeat` / `if` lights up.
- [ ] 103. **Live error squiggles** while you type, with the friendly message on hover.
- [ ] 104. **Hover help:** hover a command to see what it does, with an example.
- [ ] 105. **Number scrubbing:** Alt/Option-drag a number to change it and watch the drawing update.
- [ ] 106. **Color swatches** next to color names, with a color picker.
- [ ] 107. **Outline panel:** your commands and events, click to jump.
- [ ] 108. **Go to definition** (Ctrl/Cmd-click a command name).
- [ ] 109. **Rename everywhere** (F2).
- [ ] 110. **Format document** (fix indentation).
- [ ] 111. **Code folding** for blocks.
- [ ] 112. **Split editor:** two files side by side.
- [ ] 113. **Minimap** overview strip.
- [ ] 114. **Word wrap** and **show spaces** toggles.
- [ ] 115. **Smarter autocomplete** with your own variables and commands, plus docs.
- [ ] 116. **Sparky snippets library** (square, star, game loop, quiz…).
- [ ] 117. **Line tools:** duplicate line, move line up/down, select next match.
- [ ] 118. **Breadcrumbs** ("teach star › repeat").
- [ ] 119. **Live mode:** drawings re-run as you type.
- [ ] 120. **Auto-close** quotes and brackets.
- [ ] 121. **Zen mode** (just the code and the stage).
- [ ] 122. **Find in all files** in the open folder.
- [ ] 123. **Bookmarks** in code.
- [ ] 124. **Export code** as colored HTML (ready to print).

### F. Run and debug (125–138)

- [ ] 125. **Step:** run one line at a time.
- [ ] 126. **Breakpoints:** click the gutter to pause there.
- [ ] 127. **Variables panel:** every variable and list, updating live.
- [ ] 128. **Call stack** for `teach` commands (great for recursion).
- [ ] 129. **Line trail:** recently-run lines fade out.
- [ ] 130. **Error explanations** link to the lesson that teaches the fix.
- [ ] 131. **Forever-loop guard:** a friendly hint when a loop never waits.
- [ ] 132. **Run selection:** run just the selected lines.
- [ ] 133. **Run history:** your last 10 runs with output and time.
- [ ] 134. **Run stats:** lines run and time taken.
- [ ] 135. **Console filters:** only errors, or only says.
- [ ] 136. **Click an error** in the console to jump to its line.
- [ ] 137. **Watch expressions** (`x * 2`, `length(pets)`).
- [ ] 138. **Replay the last run** with a slider.

### G. Learn (139–160)

- [ ] 139. **30 lessons in 5 worlds:** Draw, Loops, Talk and Ask, Lists and Logic, Games.
- [ ] 140. **Check my work:** lessons check your program and drawing.
- [ ] 141. **Hints** in 3 levels for every challenge.
- [ ] 142. **Badges** for milestones (first program, first game, 100 runs…).
- [ ] 143. **Daily challenge.**
- [ ] 144. **Bug hunts:** find and fix the bug.
- [ ] 145. **Predict-the-output quizzes.**
- [ ] 146. **Progress map** with stars.
- [ ] 147. **Certificates** (PNG) for finishing a world, with your name.
- [ ] 148. **Glossary** of coding words in kid language.
- [ ] 149. **Searchable language reference.**
- [ ] 150. **Explain this line** (offline, no AI).
- [ ] 151. **Guided tour** of the app on first launch.
- [ ] 152. **Try it** buttons open lesson code in a new tab.
- [ ] 153. **Progress report** for parents and teachers (HTML).
- [ ] 154. **Python track:** lessons that move from Sparky to real Python, side by side.
- [ ] 155. **40+ examples** sorted by category.
- [ ] 156. **Templates:** Game, Story, Art, Music, Quiz.
- [ ] 157. **Lesson search.**
- [ ] 158. **Works offline:** all lessons are built in.
- [ ] 159. **Achievements screen.**
- [ ] 160. **Level-up moments:** a celebration when you finish a world.

### H. Projects and files (161–174)

- [ ] 161. **Projects folder** (`~/Sparky/Projects`) shown on the Home screen.
- [ ] 162. **Autosave,** so you never lose work.
- [ ] 163. **Version history:** restore an older version of any file.
- [ ] 164. **Thumbnails** of your stage on every project.
- [ ] 165. **Project bundles:** `.sparky` files with code, images and sounds together.
- [ ] 166. **Assets panel** for a project's images and sounds.
- [ ] 167. **Rename, duplicate or move to Trash** from the Home screen.
- [ ] 168. **Recent files.**
- [ ] 169. **Crash recovery:** unsaved tabs come back after a crash.
- [ ] 170. **File associations:** double-click a `.spark` file to open Sparky.
- [ ] 171. **Open from Finder and the Dock** on Mac.
- [ ] 172. **Share card:** a PNG with your drawing and your code.
- [ ] 173. **Make an App 2.0:** your own name and icon, a fullscreen player.
- [ ] 174. **New project dialog** with templates.

### I. Sound and music (175–182)

- [ ] 175. **Songs:** `play song "C D E F G"`.
- [ ] 176. **Instruments:** piano, xylophone, guitar, organ, flute.
- [ ] 177. **Chords:** `play chord "C E G"`.
- [ ] 178. **Tempo and rests:** `tempo 120`, `rest 1`.
- [ ] 179. **20 new sounds:** coin, splash, whoosh, meow, woof, applause and more.
- [ ] 180. **Sound library** with previews.
- [ ] 181. **Piano panel:** click keys to write notes into your code.
- [ ] 182. **Sound settings:** master volume and which events make sounds.

### J. AI helper (183–192)

- [ ] 183. **Fix with AI** button on errors (when AI is set up).
- [ ] 184. **Hint mode** (default): the AI gives hints, not full answers.
- [ ] 185. **Explain this line with AI.**
- [ ] 186. **Make me a challenge.**
- [ ] 187. **Idea to plan:** turn an idea into steps.
- [ ] 188. **Chat history** saved per project, with Clear.
- [ ] 189. **Local AI:** an Ollama preset, private and offline.
- [ ] 190. **More presets:** OpenRouter, Groq, Gemini (OpenAI-compatible).
- [ ] 191. **"What gets sent" panel** for privacy.
- [ ] 192. **Preview AI code** before it goes into your file.

### K. Extensions and personalization (193–200)

- [ ] 193. **Extension API v2:** extensions can add new Sparky commands, not just blocks.
- [ ] 194. **Extension manager:** turn extensions on and off, see details.
- [ ] 195. **Featured extensions** list (signed) from sparky-code.web.app.
- [ ] 196. **Sparky extension packs:** Shapes+, Games and Music+.
- [ ] 197. **Theme preview** before applying a VS Code theme.
- [ ] 198. **Choose the code font and size.**
- [ ] 199. **Import and export settings.**
- [ ] 200. **Mascot customizer:** pick Sparky's color.

### L. Accessibility and languages (201–210)

- [ ] 201. **High Contrast theme.**
- [ ] 202. **Readable mode:** extra letter and line spacing.
- [ ] 203. **Screen-reader labels** on every control.
- [ ] 204. **Full keyboard use** with clear focus rings.
- [ ] 205. **Reduce motion.**
- [ ] 206. **Color-blind-safe** syntax colors.
- [ ] 207. **Thicker cursor** option.
- [ ] 208. **Read aloud:** Sparky can speak console messages.
- [ ] 209. **The app in Hindi and Telugu** (beta), with a translation-ready UI.
- [ ] 210. **Left-handed layout** (stage on the left).

### M. Classroom and families (211–217)

- [ ] 211. **Classroom mode:** a PIN locks settings and can hide AI and extensions.
- [ ] 212. **Assignment files (`.sparkytask`):** instructions, starter code and checks.
- [ ] 213. **Hand-in:** export your work with your name, ready to submit.
- [ ] 214. **Break reminders** (optional, gentle).
- [ ] 215. **Offline mode:** Sparky never touches the internet.
- [ ] 216. **Time on task** (local only).
- [ ] 217. **Teacher guide** on the website.

### N. App quality and platforms (218–226)

- [ ] 218. **Crash reporter:** a friendly window with details you can copy, and a log file.
- [ ] 219. **Safe mode** (`--safe`): starts without extensions or updates.
- [ ] 220. **Logs folder** and an "Open logs" command.
- [ ] 221. **Faster startup:** panels load when first opened.
- [ ] 222. **One window:** opening a file while Sparky runs uses the open window.
- [ ] 223. **Portable Windows version** (a zip, no install).
- [ ] 224. **Diagnostics page:** versions, folders, update channel.
- [ ] 225. **Sparky Player** gets the new stage, sprites and events.
- [ ] 226. **Intel Mac build** *(later: needs a universal Python build; Apple-silicon only for now)*.

### O. Website and community (227–234)

- [ ] 227. **Docs on the web:** the language reference, generated from the app's own data.
- [ ] 228. **Release notes page** for every version.
- [ ] 229. **Featured projects page** (from the same signed feed the app uses).
- [ ] 230. **Playground upgrade:** more of the language runs in the browser, plus share links.
- [ ] 231. **News in the app** (signed feed).
- [ ] 232. **"Check your download" page:** how to verify checksums and signatures.
- [ ] 233. **FAQ page.**
- [ ] 234. **Teacher page.**

---

## What can't be done for free

- **Apple notarization / Developer ID** needs a paid Apple Developer account. The Mac app
  stays ad-hoc signed, so the first launch still needs System Settings → Privacy &
  Security → Open Anyway. Updates after that install without the warning.
- **Windows Authenticode** needs a paid code-signing certificate, so Windows still shows
  "Windows protected your PC" on the first install. OTA updates after that are verified
  by Sparky's own signature.

---

## Build plan

| Build | What's in it |
|---|---|
| 3.0.0-alpha.1 | A (updates and signing), most of B (new look), N |
| 3.0.0-alpha.2 | C (language) and D (stage and sprites) |
| 3.0.0-alpha.3 | E (editor) and F (run and debug) |
| 3.0.0-alpha.4 | G (learn) and H (projects) |
| 3.0.0-alpha.5 | I, J, K, L, M |
| 3.0.0 | O (website), the rest of B, the release |

Alphas reach Mohith's Mac over the Beta channel as small code packs. 3.0.0 ships full
installers for every platform, plus the signed Stable manifest.
