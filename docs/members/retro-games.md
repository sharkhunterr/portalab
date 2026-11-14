# Playing retro games in the portal

When your server has a **RomM** game library, its games can be played **right in Portalab**: open a game's page and tap **« Play here »**. The game starts in RomM's own emulator (EmulatorJS), so it plays as it does in RomM, without leaving the portal or signing in to RomM.

## Playing

- **« Play here »** shows on a game's page when the portal can run it — the same consoles as RomM: NES, SNES, Game Boy, GBA, Mega Drive, Master System, PlayStation, Nintendo 64, DS, PSP, arcade, Commodore, Amstrad, Atari and many more, and **Flash** games (in Ruffle) — and the library has its file. **« Play on RomM »** stays next to it.
- The game opens over the whole window. Tap **« Play »**: the page shows each step as it loads — the emulator, the console's core, its BIOS, the game, your save — with its progress, then the game starts; if something fails, it says what. The emulator's own menu (bottom bar) has its controls, full screen, save states, gamepad settings and the on-screen gamepad on a phone.
- The back arrow at the top left closes the game and brings you back to its page.
- A few consoles (DOS, PSP, 3DS) need a page isolated from other sites; Portalab's game page is. If such a game does not start, reload the page.

## Controls

- A keyboard, a **gamepad** (plugged in or Bluetooth) or, on a phone, the **on-screen gamepad** — laid out like the console's own for the Sega consoles.
- Change the controls and the emulator's options in its menu (bottom bar, *Controls* and *Settings*): they are kept **per console**, with your profile, and follow you to your other devices.

## Saves

Your progress follows **you** (your profile, in a household), on every device:

- **The game's own save** (what the game saves itself, as on the console) is kept every minute while you play and when you leave, and loaded when you play again.
- **Save states**: open **Saves** (the floppy disk at the top right while playing) and use **« Save here »** on one of the 5 slots — the slot keeps a picture of the screen — then **« Load »** whenever you want. The emulator's own *Save State* / *Load State* buttons use the slot you last chose.
- **Resume**: leaving the game keeps where you are (« Where you left off », with a picture of the screen). The game's page then offers **« Resume »** — choose the save, each shown with its picture and date — or **« New game »** (your game's own save is still there).
- Each save and state is also **copied to RomM**, labelled « Portalab » and with your name, so you find them in RomM too. A member's or a profile's saves are never another's.
- A save state is the emulator's whole memory: for the largest consoles it may exceed what the portal accepts (10 MB unless your administrator raised it).

## Your own RomM account

By default, the portal writes your play sessions, saves and states to the RomM account it uses itself (shared by everyone, each save labelled with its owner). To have them in **your own** RomM account:

1. Open *Settings › Media accounts*, card **« My game library account »**, and tap **« Authorise Portalab »** — the welcome offers it too, once your administrator linked you to your RomM account.
2. A code shows, with **« Approve in RomM »**: open it (signed in to RomM with your account) and approve the code.
3. The card says **« Your games go to your account … »**: from then on your sessions, saves and states go there (a household profile's go to its master's account, labelled with the profile).

The portal only asks RomM for what it does (who you are, your play sessions, saves and states, its device) and keeps the authorisation encrypted. **« Remove the authorisation »** revokes it (in RomM too); revoking it in RomM works as well — the portal then goes back to the shared account and asks you to authorise again.

## What counts

The time you play counts like a film watched in the portal's player: in your **statistics** (as a game played in Portalab), in your **XP** and **streak** through the gain rules, and in a household profile's **screen time**. Only the time the game runs with the page in front counts; a page left in a background tab does not.

Flash games keep their own progress in the browser (no save states).

Each game session is also told to **RomM**, which keeps the play time of the account the portal uses there. RomM's own history of that account leaves the portal's sessions out (they are counted already).

## Household profiles

A profile plays within its master's rules: a game kept out (by its title, or games as a whole) does not open, and once the profile's **screen time** of the day is spent, the game stops and a message says so — see [Household profiles](households.md).
