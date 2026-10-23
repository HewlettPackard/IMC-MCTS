from datetime import date
project = "IMC-MCTS"
author = "IMC-MCTS contributors"
copyright = "2026, IMC-MCTS contributors"
version = "0.2.0rc1"
release = version
root_doc = "index"
extensions = []
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]
html_theme = "pydata_sphinx_theme"
html_title = "IMC-MCTS documentation"
html_short_title = "IMC-MCTS"
html_logo = "_static/imc-mcts-logo.svg"
html_favicon = "_static/imc-mcts-icon.svg"
html_static_path = ["_static"]
templates_path = ["_templates"]
html_css_files = ["custom.css", "tutorial.css"]
html_js_files = []
html_copy_source = True
html_show_sourcelink = True
html_show_sphinx = True
html_sidebars = {"**": ["search-field.html", "sidebar-global.html"]}
html_theme_options = {
    "logo": {
        "image_light": "_static/imc-mcts-logo.svg",
        "image_dark": "_static/imc-mcts-logo-reversed.svg",
        "alt_text": "IMC-MCTS",
    },
    "navbar_start": ["navbar-logo"],
    "navbar_center": [],
    "navbar_end": ["theme-switcher", "navbar-icon-links"],
    "navbar_persistent": [],
    "show_nav_level": 2,
    "navigation_depth": 2,
    "collapse_navigation": False,
    "show_toc_level": 2,
    "show_prev_next": True,
    "secondary_sidebar_items": ["page-toc"],
    "footer_start": ["copyright"],
    "footer_end": ["sphinx-version", "theme-version"],
    "icon_links": [{"name": "GitHub", "url": "https://github.com/HewlettPackard/IMC-MCTS", "icon": "fa-brands fa-github"}],
}
html_context = {"default_mode": "light"}
