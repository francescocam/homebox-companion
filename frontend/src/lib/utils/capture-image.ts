import type { CaptureImageTransform } from '$lib/types';

export const CAPTURE_EXPORT_MAX_DIMENSION = 1920;
export const CAPTURE_EXPORT_QUALITY = 0.75;
export const CAPTURE_EXPORT_MIME_TYPE = 'image/jpeg';

export interface CropRect {
	x: number;
	y: number;
	width: number;
	height: number;
}

export interface CropEditorResult {
	file: File;
	transform: CaptureImageTransform;
}

export function loadImageElement(src: string): Promise<HTMLImageElement> {
	return new Promise((resolve, reject) => {
		const image = new Image();
		image.onload = () => resolve(image);
		image.onerror = () => reject(new Error('Failed to load image'));
		image.src = src;
	});
}

export function canvasToBlob(
	canvas: HTMLCanvasElement,
	type = CAPTURE_EXPORT_MIME_TYPE,
	quality = CAPTURE_EXPORT_QUALITY
): Promise<Blob> {
	return new Promise((resolve, reject) => {
		canvas.toBlob(
			(blob) => {
				if (blob) {
					resolve(blob);
				} else {
					reject(new Error('Failed to export image'));
				}
			},
			type,
			quality
		);
	});
}

export function buildEditedImageName(originalName: string): string {
	const baseName = originalName.replace(/\.[^.]+$/, '') || 'image';
	return `${baseName}_cropped.jpg`;
}

export function getOutputDimensions(
	cropAspectRatio: number,
	maxDimension = CAPTURE_EXPORT_MAX_DIMENSION
): { width: number; height: number } {
	if (cropAspectRatio >= 1) {
		return {
			width: maxDimension,
			height: Math.round(maxDimension / cropAspectRatio),
		};
	}

	return {
		width: Math.round(maxDimension * cropAspectRatio),
		height: maxDimension,
	};
}

export async function exportCroppedImage(options: {
	image: HTMLImageElement;
	originalName: string;
	transform: CaptureImageTransform;
	cropRect: CropRect;
	backgroundColor: string;
}): Promise<CropEditorResult> {
	const { image, originalName, transform, cropRect, backgroundColor } = options;
	const sourceCropMaxDimension = Math.max(cropRect.width, cropRect.height) / transform.scale;
	const outputMaxDimension = Math.max(
		1,
		Math.min(CAPTURE_EXPORT_MAX_DIMENSION, Math.round(sourceCropMaxDimension))
	);
	const { width, height } = getOutputDimensions(transform.cropAspectRatio, outputMaxDimension);
	const outputCanvas = document.createElement('canvas');
	outputCanvas.width = width;
	outputCanvas.height = height;

	const outputCtx = outputCanvas.getContext('2d');
	if (!outputCtx) {
		throw new Error('Could not prepare image export');
	}

	const outputScale = width / cropRect.width;

	outputCtx.fillStyle = backgroundColor;
	outputCtx.fillRect(0, 0, width, height);

	outputCtx.translate(width / 2, height / 2);
	outputCtx.rotate((transform.rotation * Math.PI) / 180);
	outputCtx.translate(transform.offsetX * outputScale, transform.offsetY * outputScale);
	outputCtx.scale(transform.scale * outputScale, transform.scale * outputScale);
	outputCtx.drawImage(image, -image.width / 2, -image.height / 2, image.width, image.height);

	const blob = await canvasToBlob(outputCanvas);
	const file = new File([blob], buildEditedImageName(originalName), {
		type: CAPTURE_EXPORT_MIME_TYPE,
		lastModified: Date.now(),
	});

	return { file, transform };
}
