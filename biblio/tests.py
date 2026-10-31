from django.test import TestCase
from django.urls import reverse


class AccessTests(TestCase):
    """La bibliothèque permet d'ajouter, modifier et supprimer des livres : réservée aux comptes connectés."""

    def test_anonymous_visitors_are_sent_to_the_login_page(self):
        for name, args in (("index", []), ("book_list", []), ("book_detail", [1]), ("add_book_isbn", []),
                           ("scan_barcode", []), ("add_book_manual", []), ("edit_book", [1]),
                           ("delete_book", [1]), ("ajax_search", [])):
            url = reverse(f"biblio:{name}", args=args)
            with self.subTest(url=url):
                r = self.client.get(url)
                self.assertEqual(r.status_code, 302)
                self.assertTrue(r["Location"].startswith("/accounts/login/?next="))
