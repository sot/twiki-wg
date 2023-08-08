from setuptools import setup

entry_points = {
    "console_scripts": [
        "twiki_wg_make_wg_index=twiki_wg.make_wg_index:main",
        "twiki_wg_ssawg_trending_scraper=twiki_wg.ssawg_trending_scraper:main",
    ]
}

setup(
    name="twiki_wg",
    author="John Scott III, Tom Aldcroft",
    description="Twiki trending and scraping",
    author_email="taldcroft@cfa.harvard.edu",
    use_scm_version=True,
    setup_requires=["setuptools_scm", "setuptools_scm_git_archive"],
    zip_safe=False,
    entry_points=entry_points,
    packages=["twiki_wg"],
    package_data={"twiki_wg": ["data/*.html", "task_schedule.cfg"]},
)
