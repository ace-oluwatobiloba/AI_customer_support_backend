from uuid import uuid4

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = (
        "Test the configured Django default storage by saving, reading, "
        "and deleting a small temporary object."
    )

    def handle(self, *args, **options):
        key = f"health-check/{uuid4().hex}.txt"
        expected = b"Backblaze B2 storage connectivity check."
        saved_name = None

        try:
            saved_name = default_storage.save(key, ContentFile(expected))
            if not default_storage.exists(saved_name):
                raise CommandError("Storage did not report the test object as existing.")

            with default_storage.open(saved_name, "rb") as stored_file:
                actual = stored_file.read()

            if actual != expected:
                raise CommandError("Storage read-back did not match the uploaded bytes.")

            default_storage.delete(saved_name)
            saved_name = None
            self.stdout.write(
                self.style.SUCCESS(
                    "Storage check passed: upload, existence check, read-back, "
                    "and deletion all succeeded."
                )
            )

        except CommandError:
            raise
        except Exception as exc:
            # Do not print exception details that could expose signed URLs or credentials.
            raise CommandError(
                "Storage check failed. Verify the B2 endpoint, bucket, "
                "application-key permissions, and network access."
            ) from exc
        finally:
            if saved_name:
                try:
                    default_storage.delete(saved_name)
                except Exception:
                    self.stderr.write(
                        self.style.WARNING(
                            "Warning: temporary test object cleanup failed. "
                            f"Check the object key: {saved_name}"
                        )
                    )
