# Quickstart — Search & Command Palette
1. Create a Wiki page, a News item and a private ticket; search a shared term as user A → only items A may see appear, grouped by type.
2. Stop the AI service → classic results still render; the analysis area shows an unavailable state. Break one provider (timeout) → its group shows `unavailable`, others unaffected.
3. Search with a typo and accented text → trigram/unaccent still match; with semantic enabled a synonym query returns meaning-related items.
4. Change a document's visibility to private → the next search no longer returns it for others (even before the embedding job catches up).
5. Open the palette (`Mod+K`) on a ticket page → context actions appear; type `open #123` → direct navigation; a destructive action asks for confirmation.
6. `GET /me/search-history`, clear it, confirm empty and not visible to another user.
