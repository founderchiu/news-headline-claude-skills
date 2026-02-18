"""Tests for URL normalization and canonicalization."""

import pytest
from dedup import canonicalize_url


class TestURLCanonicalization:
    """Tests for the canonicalize_url function."""

    def test_strips_utm_params(self):
        """UTM tracking parameters should be removed."""
        url = "https://example.com/article?utm_source=twitter&utm_medium=social"
        assert canonicalize_url(url) == "https://example.com/article"

    def test_strips_multiple_tracking_params(self):
        """All tracking parameters should be removed."""
        url = "https://example.com/article?utm_source=a&fbclid=b&gclid=c&ref=d"
        assert canonicalize_url(url) == "https://example.com/article"

    def test_preserves_important_params(self):
        """Non-tracking parameters should be preserved."""
        url = "https://example.com/article?id=123&page=2"
        result = canonicalize_url(url)
        assert "id=123" in result
        assert "page=2" in result

    def test_preserves_param_with_tracking_params_removed(self):
        """Important params should remain when tracking params are removed."""
        url = "https://example.com/article?id=123&utm_source=twitter"
        result = canonicalize_url(url)
        assert "id=123" in result
        assert "utm_source" not in result

    def test_normalizes_www(self):
        """www prefix should be stripped."""
        url = "https://www.example.com/article"
        assert canonicalize_url(url) == "https://example.com/article"

    def test_lowercases_domain(self):
        """Domain should be lowercased."""
        url = "https://EXAMPLE.COM/Article"
        result = canonicalize_url(url)
        assert "example.com" in result

    def test_removes_trailing_slash(self):
        """Trailing slashes should be removed from path."""
        url = "https://example.com/article/"
        assert canonicalize_url(url) == "https://example.com/article"

    def test_preserves_root_path(self):
        """Root path should remain valid."""
        url = "https://example.com/"
        result = canonicalize_url(url)
        # Should not have double slashes or issues
        assert result in ["https://example.com", "https://example.com/"]

    def test_removes_fragment(self):
        """URL fragments should be removed."""
        url = "https://example.com/article#section-2"
        assert canonicalize_url(url) == "https://example.com/article"

    def test_handles_empty_url(self):
        """Empty URLs should return empty string."""
        assert canonicalize_url("") == ""
        assert canonicalize_url(None) == ""

    def test_handles_malformed_url(self):
        """Malformed URLs should be handled gracefully."""
        # Should not raise exception
        result = canonicalize_url("not-a-url")
        assert isinstance(result, str)

    def test_same_url_different_tracking_params_match(self):
        """Same base URL with different tracking params should match."""
        url1 = "https://example.com/article?utm_source=twitter"
        url2 = "https://example.com/article?utm_source=facebook&fbclid=123"
        assert canonicalize_url(url1) == canonicalize_url(url2)


class TestAMPURLNormalization:
    """Tests for AMP URL detection and normalization."""

    def test_normalizes_amp_subdomain(self):
        """amp.example.com should normalize to example.com."""
        url = "https://amp.example.com/article"
        assert canonicalize_url(url) == "https://example.com/article"

    def test_normalizes_amp_path(self):
        """/amp/ path should be removed."""
        url = "https://example.com/amp/article"
        assert canonicalize_url(url) == "https://example.com/article"

    def test_normalizes_amp_path_end(self):
        """Trailing /amp should be removed."""
        url = "https://example.com/article/amp"
        assert canonicalize_url(url) == "https://example.com/article"

    def test_normalizes_google_amp_cache(self):
        """Google AMP cache URLs should normalize."""
        url = "https://example-com.cdn.ampproject.org/article"
        result = canonicalize_url(url)
        assert "example.com" in result


class TestMobileURLNormalization:
    """Tests for mobile URL detection and normalization."""

    def test_normalizes_m_subdomain(self):
        """m.example.com should normalize to example.com."""
        url = "https://m.example.com/article"
        assert canonicalize_url(url) == "https://example.com/article"

    def test_normalizes_mobile_subdomain(self):
        """mobile.example.com should normalize to example.com."""
        url = "https://mobile.example.com/article"
        assert canonicalize_url(url) == "https://example.com/article"
