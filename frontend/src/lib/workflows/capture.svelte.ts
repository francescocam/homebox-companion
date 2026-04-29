/**
 * CaptureService - Manages image capture state and operations
 *
 * Responsibilities:
 * - Image collection management (add, remove, update, clear)
 * - Additional images per capture (multi-angle shots)
 * - Image options (separateItems, extraInstructions)
 */

import { workflowLogger as log } from '$lib/utils/logger';
import { revokeImageObjectUrls } from '$lib/services/serialize';
import type { CapturedImage, CaptureImageTransform } from '$lib/types';

// =============================================================================
// CAPTURE SERVICE CLASS
// =============================================================================

export class CaptureService {
	/** Captured images ready for analysis */
	images = $state<CapturedImage[]>([]);

	// =========================================================================
	// IMAGE OPERATIONS
	// =========================================================================

	/** Add a captured image */
	addImage(image: CapturedImage): void {
		log.debug(`Adding image: file="${image.file.name}", size=${image.file.size} bytes`);
		this.images = [image, ...this.images];
		log.info(`Image added. Total images: ${this.images.length}`);
	}

	/** Remove an image by index */
	removeImage(index: number): void {
		const removedImage = this.images[index];
		if (removedImage) {
			log.debug(`Removing image at index ${index}: file="${removedImage.file.name}"`);
			// Revoke Object URLs to prevent memory leaks
			revokeImageObjectUrls(removedImage);
		}
		this.images = this.images.filter((_, i) => i !== index);
		log.info(`Image removed. Total images: ${this.images.length}`);
	}

	/** Update image options (separateItems, extraInstructions, assetId) */
	updateImageOptions(
		index: number,
		options: Partial<Pick<CapturedImage, 'separateItems' | 'extraInstructions' | 'assetId'>>
	): void {
		log.debug(`Updating options for image ${index}:`, options);
		this.images = this.images.map((img, i) => (i === index ? { ...img, ...options } : img));
	}

	/** Replace a primary image after crop/resize editing */
	replaceImageFile(
		index: number,
		file: File,
		dataUrl: string,
		cropTransform: CaptureImageTransform
	): void {
		log.debug(`Replacing image ${index}: file="${file.name}", size=${file.size} bytes`);
		this.images = this.images.map((img, i) =>
			i === index ? { ...img, file, dataUrl, cropTransform } : img
		);
	}

	/** Add additional images to a captured image (multi-angle shots) */
	addAdditionalImages(imageIndex: number, files: File[], dataUrls: string[]): void {
		log.debug(`Adding ${files.length} additional image(s) to image ${imageIndex}`);
		this.images = this.images.map((img, i) => {
			if (i !== imageIndex) return img;
			const newAdditionalCount = (img.additionalFiles?.length ?? 0) + files.length;
			log.info(`Image ${imageIndex} now has ${newAdditionalCount} additional image(s)`);
			return {
				...img,
				additionalFiles: [...(img.additionalFiles || []), ...files],
				additionalDataUrls: [...(img.additionalDataUrls || []), ...dataUrls],
			};
		});
	}

	/** Remove an additional image from a captured image */
	removeAdditionalImage(imageIndex: number, additionalIndex: number): void {
		log.debug(`Removing additional image ${additionalIndex} from image ${imageIndex}`);

		// Revoke Object URL for the removed additional image to prevent memory leak
		const img = this.images[imageIndex];
		if (img?.additionalDataUrls?.[additionalIndex]?.startsWith('blob:')) {
			URL.revokeObjectURL(img.additionalDataUrls[additionalIndex]);
		}

		this.images = this.images.map((img, i) => {
			if (i !== imageIndex) return img;
			return {
				...img,
				additionalFiles: img.additionalFiles?.filter((_, j) => j !== additionalIndex),
				additionalDataUrls: img.additionalDataUrls?.filter((_, j) => j !== additionalIndex),
				additionalCropTransforms: img.additionalCropTransforms?.filter(
					(_, j) => j !== additionalIndex
				),
			};
		});
	}

	/** Replace an additional image after crop/resize editing */
	replaceAdditionalImageFile(
		imageIndex: number,
		additionalIndex: number,
		file: File,
		dataUrl: string,
		cropTransform: CaptureImageTransform
	): void {
		log.debug(
			`Replacing additional image ${additionalIndex} for image ${imageIndex}: file="${file.name}", size=${file.size} bytes`
		);

		this.images = this.images.map((img, i) => {
			if (i !== imageIndex) return img;

			const additionalFiles = [...(img.additionalFiles || [])];
			const additionalDataUrls = [...(img.additionalDataUrls || [])];
			const additionalCropTransforms = [...(img.additionalCropTransforms || [])];

			additionalFiles[additionalIndex] = file;
			additionalDataUrls[additionalIndex] = dataUrl;
			additionalCropTransforms[additionalIndex] = cropTransform;

			return {
				...img,
				additionalFiles,
				additionalDataUrls,
				additionalCropTransforms,
			};
		});
	}

	/** Clear all captured images */
	clear(): void {
		log.debug(`Clearing all images (was: ${this.images.length})`);
		// Revoke all Object URLs to prevent memory leaks
		for (const image of this.images) {
			revokeImageObjectUrls(image);
		}
		this.images = [];
	}

	// =========================================================================
	// GETTERS
	// =========================================================================

	/** Check if there are any captured images */
	get hasImages(): boolean {
		return this.images.length > 0;
	}

	/** Get the count of captured images */
	get count(): number {
		return this.images.length;
	}

	/** Get an image by index */
	getImage(index: number): CapturedImage | null {
		return this.images[index] ?? null;
	}
}
