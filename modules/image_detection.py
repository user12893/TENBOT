"""
============================================================================
IMAGE DETECTION & FINGERPRINTING
============================================================================
Perceptual hashing system for detecting duplicate/spam images.

How it works:
1. When image is posted, generate multiple perceptual hashes
2. Check if hash matches known spam images
3. If new image, store hash for future detection
4. Users can report spam images
5. After X reports, image is auto-blocked

No AI required - uses pure image processing algorithms.
"""

import io
import aiohttp
import imagehash
from PIL import Image
from typing import Optional, Dict, Tuple, List
from datetime import datetime

import config
from database import get_db


class ImageDetector:
    """
    Image fingerprinting and spam detection system.

    Uses perceptual hashing to identify duplicate images even if:
    - Resized
    - Slightly cropped
    - Re-encoded (jpg vs png)
    - Minor color changes
    """

    def __init__(self):
        self.session = None  # aiohttp session for downloading images

    async def initialize(self):
        """Initialize aiohttp session."""
        if not self.session:
            self.session = aiohttp.ClientSession()

    async def close(self):
        """Close aiohttp session."""
        if self.session:
            await self.session.close()

    # ========================================================================
    # IMAGE DOWNLOADING
    # ========================================================================

    async def download_image(self, url: str) -> Optional[bytes]:
        """
        Download image from URL.

        Args:
            url: Image URL

        Returns:
            Image bytes or None if failed
        """
        if not self.session:
            await self.initialize()

        try:
            async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    return await response.read()
        except Exception as e:
            print(f"❌ Failed to download image: {e}")

        return None

    # ========================================================================
    # HASH GENERATION
    # ========================================================================

    def generate_hashes(self, image_bytes: bytes) -> Optional[Dict[str, str]]:
        """
        Generate multiple perceptual hashes for an image.

        Uses three different algorithms:
        - dHash: Difference hash (fast, good for crops/resizes)
        - pHash: Perceptual hash (best all-around, resistant to edits)
        - aHash: Average hash (fastest, less accurate)

        Args:
            image_bytes: Image file bytes

        Returns:
            Dict with hash values or None if failed
        """
        try:
            # Load image from bytes
            image = Image.open(io.BytesIO(image_bytes))

            # Convert to RGB if needed (fixes PNG transparency issues)
            if image.mode != 'RGB':
                image = image.convert('RGB')

            # Generate all three hash types
            hashes = {
                'dhash': str(imagehash.dhash(image)),
                'phash': str(imagehash.phash(image)),
                'average_hash': str(imagehash.average_hash(image))
            }

            return hashes

        except Exception as e:
            print(f"❌ Failed to generate hash: {e}")
            return None

    def calculate_similarity(self, hash1: str, hash2: str) -> float:
        """
        Calculate similarity between two hashes (0-100%).

        Args:
            hash1: First hash string
            hash2: Second hash string

        Returns:
            Similarity percentage (100 = identical)
        """
        try:
            # Convert hex strings back to hash objects
            h1 = imagehash.hex_to_hash(hash1)
            h2 = imagehash.hex_to_hash(hash2)

            # Calculate Hamming distance (number of different bits)
            distance = h1 - h2

            # Convert to similarity percentage
            # pHash is 64 bits, so max distance is 64
            max_distance = 64
            similarity = ((max_distance - distance) / max_distance) * 100

            return max(0, min(100, similarity))

        except Exception as e:
            print(f"❌ Failed to calculate similarity: {e}")
            return 0

    # ========================================================================
    # SPAM DETECTION
    # ========================================================================

    async def check_image(
        self,
        image_url: str,
        user_id: str,
        channel_id: str,
        message_id: str,
        filename: str
    ) -> Tuple[bool, Optional[str], Optional[Dict]]:
        """
        Check if an image is spam.

        Args:
            image_url: URL to image
            user_id: User who posted
            channel_id: Channel where posted
            message_id: Message ID
            filename: Original filename

        Returns:
            Tuple of (is_spam, reason, image_data)
        """
        db = await get_db()

        # Download image
        image_bytes = await self.download_image(image_url)
        if not image_bytes:
            return False, None, None

        # Check file size
        file_size_mb = len(image_bytes) / (1024 * 1024)
        if file_size_mb > config.MAX_IMAGE_SIZE_MB:
            return True, f"Image too large ({file_size_mb:.1f}MB)", None

        # Generate hashes
        hashes = self.generate_hashes(image_bytes)
        if not hashes:
            return False, "Could not process image", None

        # Check against known spam images
        existing = await db.find_image_by_hash(hashes['phash'])

        if existing:
            # Image has been seen before
            if existing['is_spam']:
                # Known spam image
                return True, f"Known spam image (category: {existing['spam_category']})", existing

            # Not spam, but seen before - update stats
            await db.execute(
                "UPDATE image_fingerprints SET times_posted = times_posted + 1 WHERE phash = ?",
                (hashes['phash'],)
            )
            return False, "Image seen before (allowed)", existing

        # New image - add to database
        fingerprint_id = await db.add_image_fingerprint(
            dhash=hashes['dhash'],
            phash=hashes['phash'],
            average_hash=hashes['average_hash'],
            original_url=image_url,
            filename=filename,
            user_id=user_id,
            channel_id=channel_id,
            message_id=message_id,
            is_spam=False
        )

        return False, "New image (allowed)", {
            'fingerprint_id': fingerprint_id,
            **hashes
        }

    async def check_multiple_images(
        self,
        attachments: List,
        user_id: str,
        channel_id: str,
        message_id: str
    ) -> List[Tuple[str, bool, str]]:
        """
        Check multiple images from a message.

        Args:
            attachments: List of Discord attachment objects
            user_id: User who posted
            channel_id: Channel ID
            message_id: Message ID

        Returns:
            List of (filename, is_spam, reason) tuples
        """
        results = []

        for attachment in attachments:
            # Check if it's an image
            if not attachment.filename.lower().endswith(tuple(f'.{fmt}' for fmt in config.ALLOWED_IMAGE_FORMATS)):
                continue

            is_spam, reason, data = await self.check_image(
                attachment.url,
                user_id,
                channel_id,
                message_id,
                attachment.filename
            )

            results.append((attachment.filename, is_spam, reason))

        return results

    # ========================================================================
    # USER REPORTING
    # ========================================================================

    async def report_image(
        self,
        message_id: str,
        reported_by: str,
        report_reason: str,
        channel_id: str
    ) -> Dict:
        """
        User reports an image as spam.

        Args:
            message_id: Message containing spam image
            reported_by: User ID of reporter
            report_reason: Why they're reporting it
            channel_id: Channel ID

        Returns:
            Dict with report status
        """
        db = await get_db()

        # Find image fingerprint from message
        image = await db.fetch_one(
            "SELECT * FROM image_fingerprints WHERE first_seen_message_id = ?",
            (message_id,)
        )

        if not image:
            return {
                'success': False,
                'reason': 'Image not found in database'
            }

        # Add report
        await db.execute(
            """
            INSERT INTO image_reports (fingerprint_id, reported_by, report_reason, message_id, channel_id)
            VALUES (?, ?, ?, ?, ?)
            """,
            (image['fingerprint_id'], reported_by, report_reason, message_id, channel_id)
        )

        # Update report count
        await db.execute(
            """
            UPDATE image_fingerprints
            SET report_count = report_count + 1
            WHERE fingerprint_id = ?
            """,
            (image['fingerprint_id'],)
        )

        # Get new report count
        report_count = await db.fetch_value(
            "SELECT report_count FROM image_fingerprints WHERE fingerprint_id = ?",
            (image['fingerprint_id'],)
        )

        # Auto-block if threshold reached
        auto_blocked = False
        if report_count >= config.COMMUNITY_REPORT_THRESHOLD:
            await db.execute(
                """
                UPDATE image_fingerprints
                SET is_spam = 1, spam_category = 'community_reported', auto_delete = 1
                WHERE fingerprint_id = ?
                """,
                (image['fingerprint_id'],)
            )
            auto_blocked = True

        return {
            'success': True,
            'report_count': report_count,
            'auto_blocked': auto_blocked,
            'threshold': config.COMMUNITY_REPORT_THRESHOLD
        }

    async def whitelist_image(self, phash: str) -> bool:
        """
        Mark an image as safe (remove from spam list).

        Args:
            phash: Perceptual hash of image

        Returns:
            True if successful
        """
        db = await get_db()

        try:
            await db.execute(
                """
                UPDATE image_fingerprints
                SET is_spam = 0, spam_category = NULL, auto_delete = 0, report_count = 0
                WHERE phash = ?
                """,
                (phash,)
            )
            return True
        except Exception as e:
            print(f"❌ Failed to whitelist image: {e}")
            return False

    async def blacklist_image(self, phash: str, category: str = 'manual') -> bool:
        """
        Mark an image as spam (block future posts).

        Args:
            phash: Perceptual hash of image
            category: Spam category

        Returns:
            True if successful
        """
        db = await get_db()

        try:
            await db.execute(
                """
                UPDATE image_fingerprints
                SET is_spam = 1, spam_category = ?, auto_delete = 1
                WHERE phash = ?
                """,
                (category, phash)
            )
            return True
        except Exception as e:
            print(f"❌ Failed to blacklist image: {e}")
            return False

    # ========================================================================
    # STATISTICS
    # ========================================================================

    async def get_image_stats(self) -> Dict:
        """
        Get statistics about image detection.

        Returns:
            Dict with various statistics
        """
        db = await get_db()

        total_images = await db.fetch_value(
            "SELECT COUNT(*) FROM image_fingerprints"
        )

        spam_images = await db.fetch_value(
            "SELECT COUNT(*) FROM image_fingerprints WHERE is_spam = 1"
        )

        total_reports = await db.fetch_value(
            "SELECT COUNT(*) FROM image_reports"
        )

        images_blocked_today = await db.fetch_value(
            """
            SELECT COUNT(*) FROM image_fingerprints
            WHERE is_spam = 1 AND first_seen_at > datetime('now', '-1 day')
            """
        )

        return {
            'total_images': total_images or 0,
            'spam_images': spam_images or 0,
            'clean_images': (total_images or 0) - (spam_images or 0),
            'total_reports': total_reports or 0,
            'blocked_today': images_blocked_today or 0,
            'spam_percentage': round((spam_images / total_images * 100) if total_images else 0, 1)
        }

    async def find_image_by_message(self, message_id: str) -> Optional[Dict]:
        """
        Find image fingerprint by message ID.

        Args:
            message_id: Discord message ID

        Returns:
            Image data or None
        """
        db = await get_db()
        return await db.fetch_one(
            "SELECT * FROM image_fingerprints WHERE first_seen_message_id = ?",
            (message_id,)
        )


# ============================================================================
# SINGLETON INSTANCE
# ============================================================================

# Global image detector instance
image_detector: Optional[ImageDetector] = None


async def get_image_detector() -> ImageDetector:
    """Get global image detector instance."""
    global image_detector
    if image_detector is None:
        image_detector = ImageDetector()
        await image_detector.initialize()
    return image_detector
