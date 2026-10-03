"""Content helper permissions: none of its own — uploading needs the owner domain's edit permission
(``wiki.edit`` for wiki pages, ``news.modify`` for articles), reading needs read access to the owner."""

OWNER = "module:content"
SELF = "users.self.manage"
EDIT_PERMISSION = {"wiki": "wiki.edit", "news": "news.modify"}
