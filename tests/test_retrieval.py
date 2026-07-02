from app.catalog import catalog_by_url, load_catalog
from app.retrieval import get_retriever


def test_catalog_loaded() -> None:
    catalog = load_catalog()
    assert len(catalog) == 377
    assert all(item.name and item.url and item.test_type for item in catalog)


def test_retrieval_java() -> None:
    results = get_retriever().search("senior Java Spring SQL engineer", limit=5)
    names = [item.name for item in results]
    assert any("Java" in name for name in names)


def test_recommendation_urls_are_catalog_urls() -> None:
    catalog_urls = set(catalog_by_url())
    results = get_retriever().search("Excel and Word admin assistant", limit=10)
    assert results
    assert all(item.url in catalog_urls for item in results)

