<script lang="ts">
	import { onMount } from 'svelte';
	import { Check, Crop, RotateCcw, RotateCw, Search, Sparkles, X } from 'lucide-svelte';
	import Button from './Button.svelte';
	import { CANVAS_COLORS } from '$lib/utils/canvas-colors';
	import {
		exportCroppedImage,
		loadImageElement,
		type CropEditorResult,
		type CropRect,
	} from '$lib/utils/capture-image';
	import type { CaptureImageTransform } from '$lib/types';

	interface Props {
		file: File;
		dataUrl: string;
		title: string;
		onSave: (result: CropEditorResult) => void;
		onClose: () => void;
	}

	let { file, dataUrl, title, onSave, onClose }: Props = $props();

	let canvas: HTMLCanvasElement;
	let ctx: CanvasRenderingContext2D | null = null;
	let loadedImage = $state<HTMLImageElement | null>(null);
	let canvasSize = $state(340);
	let isMovingCrop = $state(false);
	let isResizingCrop = $state(false);
	let isSaving = $state(false);
	let error = $state<string | null>(null);

	let scale = $state(1);
	let rotation = $state(0);
	let offsetX = $state(0);
	let offsetY = $state(0);
	let minScale = $state(0.1);
	let cropSizeRatio = $state(0.86);
	let cropAspectRatio = $state(1);
	let cropCenterX = $state(170);
	let cropCenterY = $state(170);

	let lastX = 0;
	let lastY = 0;
	let lastTouchDistance = 0;
	let lastTouchAngle = 0;

	const MAX_SCALE = 5;
	const MIN_ROTATION = -180;
	const MAX_ROTATION = 180;
	const MIN_CROP_SIZE_RATIO = 0.35;
	const MAX_CROP_SIZE_RATIO = 0.92;
	const CROP_HANDLE_HIT_SIZE = 34;
	const CROP_BORDER_HIT_SIZE = 20;

	type AspectMode = 'original' | 'square' | 'wide' | 'free';
	let aspectMode = $state<AspectMode>('original');
	let freeAspectRatio = $state(1);

	let cropRect = $derived.by<CropRect>(() => {
		const boundedCropSizeRatio = Math.max(
			MIN_CROP_SIZE_RATIO,
			Math.min(MAX_CROP_SIZE_RATIO, cropSizeRatio)
		);
		const maxWidth = Math.round(canvasSize * boundedCropSizeRatio);
		const maxHeight = Math.round(canvasSize * boundedCropSizeRatio);
		let width = maxWidth;
		let height = Math.round(width / cropAspectRatio);

		if (height > maxHeight) {
			height = maxHeight;
			width = Math.round(height * cropAspectRatio);
		}

		return {
			x: Math.round(clamp(cropCenterX - width / 2, 0, canvasSize - width)),
			y: Math.round(clamp(cropCenterY - height / 2, 0, canvasSize - height)),
			width,
			height,
		};
	});
	let zoomSliderValue = $derived(scaleToSlider(scale));

	onMount(() => {
		const viewportWidth = window.innerWidth;
		canvasSize =
			viewportWidth >= 640 ? Math.min(520, viewportWidth - 96) : Math.min(440, viewportWidth - 32);
		cropCenterX = canvasSize / 2;
		cropCenterY = canvasSize / 2;

		requestAnimationFrame(async () => {
			ctx = canvas.getContext('2d');
			try {
				loadedImage = await loadImageElement(dataUrl);
				cropAspectRatio = loadedImage.width / loadedImage.height;
				freeAspectRatio = cropAspectRatio;
				applyAutoSuggestion();
			} catch (loadError) {
				error = loadError instanceof Error ? loadError.message : 'Could not load image';
			}
		});
	});

	function scaleToSlider(value: number): number {
		const logBase = getMaxScale() / minScale;
		if (logBase <= 1) return 0;
		return Math.log(value / minScale) / Math.log(logBase);
	}

	function sliderToScale(value: number): number {
		const logBase = getMaxScale() / minScale;
		if (logBase <= 1) return minScale;
		return minScale * Math.pow(logBase, value);
	}

	function getMaxScale(): number {
		return Math.max(MAX_SCALE, minScale);
	}

	function getMinimumScale(): number {
		if (!loadedImage) return 0.1;
		return Math.max(cropRect.width / loadedImage.width, cropRect.height / loadedImage.height);
	}

	function updateMinimumScale() {
		minScale = getMinimumScale();
		scale = Math.max(scale, minScale);
	}

	function applyAutoSuggestion() {
		if (!loadedImage) return;

		updateMinimumScale();
		const suggestedBounds = detectContentBounds(loadedImage);
		rotation = 0;

		if (suggestedBounds) {
			scale = Math.max(
				minScale,
				Math.min(
					getMaxScale(),
					Math.max(cropRect.width / suggestedBounds.width, cropRect.height / suggestedBounds.height)
				)
			);
			const imageCenterX = loadedImage.width / 2;
			const imageCenterY = loadedImage.height / 2;
			const boundsCenterX = suggestedBounds.x + suggestedBounds.width / 2;
			const boundsCenterY = suggestedBounds.y + suggestedBounds.height / 2;
			offsetX = -(boundsCenterX - imageCenterX) * scale;
			offsetY = -(boundsCenterY - imageCenterY) * scale;
		} else {
			scale = minScale;
			offsetX = 0;
			offsetY = 0;
		}

		render();
	}

	function setAspectMode(mode: AspectMode) {
		if (!loadedImage) return;

		aspectMode = mode;
		if (mode === 'original') {
			cropAspectRatio = loadedImage.width / loadedImage.height;
			freeAspectRatio = cropAspectRatio;
		} else if (mode === 'square') {
			cropAspectRatio = 1;
			freeAspectRatio = 1;
		} else if (mode === 'wide') {
			cropAspectRatio = 16 / 9;
			freeAspectRatio = 16 / 9;
		} else {
			cropAspectRatio = freeAspectRatio;
		}

		updateMinimumScale();
		render();
	}

	function handleCropSizeSlider(e: Event) {
		cropSizeRatio = parseFloat((e.target as HTMLInputElement).value);
		updateMinimumScale();
		render();
	}

	function handleAspectSlider(e: Event) {
		freeAspectRatio = parseFloat((e.target as HTMLInputElement).value);
		aspectMode = 'free';
		cropAspectRatio = freeAspectRatio;
		updateMinimumScale();
		render();
	}

	function clamp(value: number, min: number, max: number): number {
		return Math.max(min, Math.min(max, value));
	}

	function getCanvasPoint(clientX: number, clientY: number): { x: number; y: number } {
		const rect = canvas.getBoundingClientRect();
		return {
			x: ((clientX - rect.left) / rect.width) * canvasSize,
			y: ((clientY - rect.top) / rect.height) * canvasSize,
		};
	}

	function isNearCropHandle(point: { x: number; y: number }): boolean {
		const corners = [
			{ x: cropRect.x, y: cropRect.y },
			{ x: cropRect.x + cropRect.width, y: cropRect.y },
			{ x: cropRect.x, y: cropRect.y + cropRect.height },
			{ x: cropRect.x + cropRect.width, y: cropRect.y + cropRect.height },
		];

		return corners.some(
			(corner) =>
				Math.abs(point.x - corner.x) <= CROP_HANDLE_HIT_SIZE &&
				Math.abs(point.y - corner.y) <= CROP_HANDLE_HIT_SIZE
		);
	}

	function isNearCropBorder(point: { x: number; y: number }): boolean {
		const withinHorizontalRange =
			point.x >= cropRect.x - CROP_BORDER_HIT_SIZE &&
			point.x <= cropRect.x + cropRect.width + CROP_BORDER_HIT_SIZE;
		const withinVerticalRange =
			point.y >= cropRect.y - CROP_BORDER_HIT_SIZE &&
			point.y <= cropRect.y + cropRect.height + CROP_BORDER_HIT_SIZE;
		const nearLeft = Math.abs(point.x - cropRect.x) <= CROP_BORDER_HIT_SIZE;
		const nearRight = Math.abs(point.x - (cropRect.x + cropRect.width)) <= CROP_BORDER_HIT_SIZE;
		const nearTop = Math.abs(point.y - cropRect.y) <= CROP_BORDER_HIT_SIZE;
		const nearBottom = Math.abs(point.y - (cropRect.y + cropRect.height)) <= CROP_BORDER_HIT_SIZE;

		return (
			((nearLeft || nearRight) && withinVerticalRange) ||
			((nearTop || nearBottom) && withinHorizontalRange)
		);
	}

	function canResizeCropFromPoint(point: { x: number; y: number }): boolean {
		return isNearCropHandle(point) || isNearCropBorder(point);
	}

	function resizeCropFromPoint(point: { x: number; y: number }) {
		const desiredWidth = clamp(
			Math.abs(point.x - cropCenterX) * 2,
			canvasSize * MIN_CROP_SIZE_RATIO,
			canvasSize * MAX_CROP_SIZE_RATIO
		);
		const desiredHeight = clamp(
			Math.abs(point.y - cropCenterY) * 2,
			canvasSize * MIN_CROP_SIZE_RATIO,
			canvasSize * MAX_CROP_SIZE_RATIO
		);

		if (aspectMode === 'free') {
			freeAspectRatio = clamp(desiredWidth / desiredHeight, 0.5, 2);
			cropAspectRatio = freeAspectRatio;
			cropSizeRatio = clamp(
				Math.max(desiredWidth, desiredHeight) / canvasSize,
				MIN_CROP_SIZE_RATIO,
				MAX_CROP_SIZE_RATIO
			);
		} else {
			cropSizeRatio = clamp(
				Math.max(desiredWidth, desiredHeight) / canvasSize,
				MIN_CROP_SIZE_RATIO,
				MAX_CROP_SIZE_RATIO
			);
		}

		updateMinimumScale();
		clampCropCenter();
		render();
	}

	function isInsideCrop(point: { x: number; y: number }): boolean {
		return (
			point.x > cropRect.x + CROP_BORDER_HIT_SIZE &&
			point.x < cropRect.x + cropRect.width - CROP_BORDER_HIT_SIZE &&
			point.y > cropRect.y + CROP_BORDER_HIT_SIZE &&
			point.y < cropRect.y + cropRect.height - CROP_BORDER_HIT_SIZE
		);
	}

	function clampCropCenter() {
		cropCenterX = clamp(cropCenterX, cropRect.width / 2, canvasSize - cropRect.width / 2);
		cropCenterY = clamp(cropCenterY, cropRect.height / 2, canvasSize - cropRect.height / 2);
	}

	function moveCropBy(dx: number, dy: number) {
		cropCenterX += dx;
		cropCenterY += dy;
		clampCropCenter();
		render();
	}

	function detectContentBounds(image: HTMLImageElement): CropRect | null {
		const sampleSize = 160;
		const sampleCanvas = document.createElement('canvas');
		const ratio = image.width / image.height;
		sampleCanvas.width = ratio >= 1 ? sampleSize : Math.max(1, Math.round(sampleSize * ratio));
		sampleCanvas.height = ratio >= 1 ? Math.max(1, Math.round(sampleSize / ratio)) : sampleSize;

		const sampleCtx = sampleCanvas.getContext('2d', { willReadFrequently: true });
		if (!sampleCtx) return null;

		sampleCtx.drawImage(image, 0, 0, sampleCanvas.width, sampleCanvas.height);
		const { data } = sampleCtx.getImageData(0, 0, sampleCanvas.width, sampleCanvas.height);
		const border = averageBorderColor(data, sampleCanvas.width, sampleCanvas.height);
		const threshold = 34;
		let minX = sampleCanvas.width;
		let minY = sampleCanvas.height;
		let maxX = -1;
		let maxY = -1;

		for (let y = 0; y < sampleCanvas.height; y++) {
			for (let x = 0; x < sampleCanvas.width; x++) {
				const index = (y * sampleCanvas.width + x) * 4;
				const diff =
					Math.abs(data[index] - border.r) +
					Math.abs(data[index + 1] - border.g) +
					Math.abs(data[index + 2] - border.b);

				if (diff > threshold) {
					minX = Math.min(minX, x);
					minY = Math.min(minY, y);
					maxX = Math.max(maxX, x);
					maxY = Math.max(maxY, y);
				}
			}
		}

		if (maxX < 0 || maxY < 0) return null;

		const width = maxX - minX + 1;
		const height = maxY - minY + 1;
		const imageArea = sampleCanvas.width * sampleCanvas.height;
		const boundsArea = width * height;

		if (boundsArea / imageArea > 0.92 || boundsArea / imageArea < 0.08) {
			return null;
		}

		const padding = Math.round(Math.max(sampleCanvas.width, sampleCanvas.height) * 0.05);
		minX = Math.max(0, minX - padding);
		minY = Math.max(0, minY - padding);
		maxX = Math.min(sampleCanvas.width - 1, maxX + padding);
		maxY = Math.min(sampleCanvas.height - 1, maxY + padding);

		const scaleX = image.width / sampleCanvas.width;
		const scaleY = image.height / sampleCanvas.height;
		return {
			x: minX * scaleX,
			y: minY * scaleY,
			width: (maxX - minX + 1) * scaleX,
			height: (maxY - minY + 1) * scaleY,
		};
	}

	function averageBorderColor(
		data: Uint8ClampedArray,
		width: number,
		height: number
	): { r: number; g: number; b: number } {
		let r = 0;
		let g = 0;
		let b = 0;
		let count = 0;

		function addPixel(x: number, y: number) {
			const index = (y * width + x) * 4;
			r += data[index];
			g += data[index + 1];
			b += data[index + 2];
			count++;
		}

		for (let x = 0; x < width; x++) {
			addPixel(x, 0);
			addPixel(x, height - 1);
		}
		for (let y = 1; y < height - 1; y++) {
			addPixel(0, y);
			addPixel(width - 1, y);
		}

		return { r: r / count, g: g / count, b: b / count };
	}

	function render() {
		if (!ctx || !loadedImage) return;

		ctx.fillStyle = CANVAS_COLORS.background;
		ctx.fillRect(0, 0, canvasSize, canvasSize);

		ctx.save();
		ctx.translate(canvasSize / 2, canvasSize / 2);
		ctx.rotate((rotation * Math.PI) / 180);
		ctx.translate(offsetX, offsetY);
		ctx.scale(scale, scale);
		ctx.drawImage(
			loadedImage,
			-loadedImage.width / 2,
			-loadedImage.height / 2,
			loadedImage.width,
			loadedImage.height
		);
		ctx.restore();

		ctx.fillStyle = CANVAS_COLORS.dimOverlay;
		ctx.fillRect(0, 0, canvasSize, cropRect.y);
		ctx.fillRect(
			0,
			cropRect.y + cropRect.height,
			canvasSize,
			canvasSize - cropRect.y - cropRect.height
		);
		ctx.fillRect(0, cropRect.y, cropRect.x, cropRect.height);
		ctx.fillRect(
			cropRect.x + cropRect.width,
			cropRect.y,
			canvasSize - cropRect.x - cropRect.width,
			cropRect.height
		);

		ctx.strokeStyle = CANVAS_COLORS.primaryOverlay;
		ctx.lineWidth = 2;
		ctx.strokeRect(cropRect.x, cropRect.y, cropRect.width, cropRect.height);

		const handleSize = 22;
		ctx.strokeStyle = CANVAS_COLORS.primary;
		ctx.lineWidth = 3;
		drawCorner(cropRect.x, cropRect.y, handleSize, 1, 1);
		drawCorner(cropRect.x + cropRect.width, cropRect.y, handleSize, -1, 1);
		drawCorner(cropRect.x, cropRect.y + cropRect.height, handleSize, 1, -1);
		drawCorner(cropRect.x + cropRect.width, cropRect.y + cropRect.height, handleSize, -1, -1);
		drawHandle(cropRect.x, cropRect.y);
		drawHandle(cropRect.x + cropRect.width, cropRect.y);
		drawHandle(cropRect.x, cropRect.y + cropRect.height);
		drawHandle(cropRect.x + cropRect.width, cropRect.y + cropRect.height);
	}

	function drawCorner(x: number, y: number, size: number, xDirection: 1 | -1, yDirection: 1 | -1) {
		if (!ctx) return;
		ctx.beginPath();
		ctx.moveTo(x, y + size * yDirection);
		ctx.lineTo(x, y);
		ctx.lineTo(x + size * xDirection, y);
		ctx.stroke();
	}

	function drawHandle(x: number, y: number) {
		if (!ctx) return;
		ctx.fillStyle = CANVAS_COLORS.primary;
		ctx.strokeStyle = CANVAS_COLORS.background;
		ctx.lineWidth = 2;
		ctx.beginPath();
		ctx.roundRect(x - 6, y - 6, 12, 12, 3);
		ctx.fill();
		ctx.stroke();
	}

	function handleMouseDown(e: MouseEvent) {
		const point = getCanvasPoint(e.clientX, e.clientY);
		if (canResizeCropFromPoint(point)) {
			isResizingCrop = true;
			isMovingCrop = false;
			canvas.style.cursor = 'nwse-resize';
			resizeCropFromPoint(point);
		} else if (isInsideCrop(point)) {
			isMovingCrop = true;
			isResizingCrop = false;
			lastX = e.clientX;
			lastY = e.clientY;
			canvas.style.cursor = 'move';
		}
	}

	function handleMouseMove(e: MouseEvent) {
		if (isResizingCrop) {
			resizeCropFromPoint(getCanvasPoint(e.clientX, e.clientY));
			return;
		}

		if (isMovingCrop) {
			const rect = canvas.getBoundingClientRect();
			const dx = ((e.clientX - lastX) / rect.width) * canvasSize;
			const dy = ((e.clientY - lastY) / rect.height) * canvasSize;
			moveCropBy(dx, dy);
			lastX = e.clientX;
			lastY = e.clientY;
			return;
		}

		const point = getCanvasPoint(e.clientX, e.clientY);
		canvas.style.cursor = canResizeCropFromPoint(point)
			? 'nwse-resize'
			: isInsideCrop(point)
				? 'move'
				: 'default';
	}

	function handleMouseUp() {
		isResizingCrop = false;
		isMovingCrop = false;
		canvas.style.cursor = 'default';
	}

	function handleWheel(e: WheelEvent) {
		e.preventDefault();
		const delta = e.deltaY > 0 ? 0.95 : 1.05;
		scale = Math.max(minScale, Math.min(getMaxScale(), scale * delta));
		render();
	}

	function handleTouchStart(e: TouchEvent) {
		e.preventDefault();
		if (e.touches.length === 1) {
			const point = getCanvasPoint(e.touches[0].clientX, e.touches[0].clientY);
			if (canResizeCropFromPoint(point)) {
				isResizingCrop = true;
				isMovingCrop = false;
				resizeCropFromPoint(point);
			} else if (isInsideCrop(point)) {
				isMovingCrop = true;
				isResizingCrop = false;
				lastX = e.touches[0].clientX;
				lastY = e.touches[0].clientY;
			} else {
				isMovingCrop = false;
				isResizingCrop = false;
			}
		} else if (e.touches.length === 2) {
			isMovingCrop = false;
			isResizingCrop = false;
			lastTouchDistance = getTouchDistance(e.touches);
			lastTouchAngle = getTouchAngle(e.touches);
		}
	}

	function handleTouchMove(e: TouchEvent) {
		e.preventDefault();
		if (e.touches.length === 1 && isResizingCrop) {
			resizeCropFromPoint(getCanvasPoint(e.touches[0].clientX, e.touches[0].clientY));
		} else if (e.touches.length === 1 && isMovingCrop) {
			const rect = canvas.getBoundingClientRect();
			const dx = ((e.touches[0].clientX - lastX) / rect.width) * canvasSize;
			const dy = ((e.touches[0].clientY - lastY) / rect.height) * canvasSize;
			moveCropBy(dx, dy);
			lastX = e.touches[0].clientX;
			lastY = e.touches[0].clientY;
		} else if (e.touches.length === 2) {
			const newDistance = getTouchDistance(e.touches);
			const scaleChange = newDistance / lastTouchDistance;
			scale = Math.max(minScale, Math.min(getMaxScale(), scale * scaleChange));
			lastTouchDistance = newDistance;

			const newAngle = getTouchAngle(e.touches);
			const angleDelta = (newAngle - lastTouchAngle) * (180 / Math.PI);
			rotation = Math.max(MIN_ROTATION, Math.min(MAX_ROTATION, rotation + angleDelta));
			lastTouchAngle = newAngle;
		}
		render();
	}

	function handleTouchEnd(e: TouchEvent) {
		if (e.touches.length === 0) {
			isMovingCrop = false;
			isResizingCrop = false;
		} else if (e.touches.length === 1) {
			isMovingCrop = false;
			isResizingCrop = false;
		}
	}

	function getTouchDistance(touches: TouchList): number {
		const dx = touches[0].clientX - touches[1].clientX;
		const dy = touches[0].clientY - touches[1].clientY;
		return Math.sqrt(dx * dx + dy * dy);
	}

	function getTouchAngle(touches: TouchList): number {
		const dx = touches[1].clientX - touches[0].clientX;
		const dy = touches[1].clientY - touches[0].clientY;
		return Math.atan2(dy, dx);
	}

	function handleZoomSlider(e: Event) {
		scale = sliderToScale(parseFloat((e.target as HTMLInputElement).value));
		render();
	}

	function handleRotationSlider(e: Event) {
		rotation = parseFloat((e.target as HTMLInputElement).value);
		render();
	}

	function rotateLeft90() {
		rotation = Math.max(MIN_ROTATION, rotation - 90);
		render();
	}

	function rotateRight90() {
		rotation = Math.min(MAX_ROTATION, rotation + 90);
		render();
	}

	async function saveCrop() {
		if (!loadedImage || isSaving) return;
		isSaving = true;
		error = null;

		try {
			const transform: CaptureImageTransform = {
				scale,
				rotation,
				offsetX,
				offsetY,
				cropAspectRatio,
				cropCenterX,
				cropCenterY,
				edited: true,
			};
			const result = await exportCroppedImage({
				image: loadedImage,
				originalName: file.name,
				transform,
				cropRect,
				backgroundColor: CANVAS_COLORS.background,
			});
			onSave(result);
		} catch (saveError) {
			error = saveError instanceof Error ? saveError.message : 'Could not save cropped image';
		} finally {
			isSaving = false;
		}
	}
</script>

<div
	class="fixed inset-0 z-modal flex items-start justify-center overflow-y-auto bg-neutral-950/80 p-4 sm:p-8"
>
	<div
		class="my-auto w-full max-w-xl rounded-xl border border-neutral-700 bg-neutral-900 shadow-xl sm:my-8"
	>
		<div class="flex items-center justify-between border-b border-neutral-700 p-4">
			<div class="min-w-0">
				<h3 class="text-body-lg font-semibold text-neutral-100">Crop Photo</h3>
				<p class="truncate text-caption text-neutral-400">{title}</p>
			</div>
			<button
				type="button"
				class="flex min-h-touch min-w-touch items-center justify-center rounded-lg p-2 text-neutral-400 transition-colors hover:bg-neutral-800 hover:text-neutral-100"
				onclick={onClose}
				aria-label="Close crop editor"
			>
				<X size={20} strokeWidth={1.5} />
			</button>
		</div>

		<div class="border-b border-neutral-700/50 bg-neutral-800/50 px-4 py-2">
			<p class="text-center text-caption text-neutral-400">
				Drag inside the crop box to move it. Drag the border to resize.
			</p>
		</div>

		<div class="flex touch-none items-center justify-center p-4">
			<canvas
				bind:this={canvas}
				width={canvasSize}
				height={canvasSize}
				class="rounded-lg {isResizingCrop ? 'cursor-nwse-resize' : ''} {isMovingCrop
					? 'cursor-move'
					: ''}"
				onmousedown={handleMouseDown}
				onmousemove={handleMouseMove}
				onmouseup={handleMouseUp}
				onmouseleave={handleMouseUp}
				onwheel={handleWheel}
				ontouchstart={handleTouchStart}
				ontouchmove={handleTouchMove}
				ontouchend={handleTouchEnd}
			></canvas>
		</div>

		{#if error}
			<div
				class="text-error-200 mx-4 mb-3 rounded-lg border border-error-500/30 bg-error-500/10 px-3 py-2 text-body-sm"
			>
				{error}
			</div>
		{/if}

		<div class="space-y-5 border-t border-neutral-700/50 px-4 py-4">
			<div>
				<label
					for="captureCropSizeSlider"
					class="mb-2 flex items-center gap-1.5 text-caption font-medium text-neutral-300"
				>
					<Crop class="text-primary-400" size={16} strokeWidth={1.5} />
					Crop Size
				</label>
				<input
					id="captureCropSizeSlider"
					type="range"
					min={MIN_CROP_SIZE_RATIO}
					max={MAX_CROP_SIZE_RATIO}
					step="0.01"
					value={cropSizeRatio}
					oninput={handleCropSizeSlider}
					class="slider-primary h-2 w-full cursor-pointer rounded-lg bg-neutral-800"
				/>
			</div>

			<div>
				<div class="mb-2 flex items-center justify-between">
					<span class="text-caption font-medium text-neutral-300">Crop Shape</span>
					<span class="text-xxs text-neutral-500">{cropRect.width} x {cropRect.height}</span>
				</div>
				<div class="grid grid-cols-4 gap-2">
					<button
						type="button"
						class="min-h-touch rounded-lg px-2 py-2 text-caption transition-colors {aspectMode ===
						'original'
							? 'bg-primary-600 text-neutral-100'
							: 'bg-neutral-800 text-neutral-300 hover:bg-neutral-700'}"
						onclick={() => setAspectMode('original')}
					>
						Original
					</button>
					<button
						type="button"
						class="min-h-touch rounded-lg px-2 py-2 text-caption transition-colors {aspectMode ===
						'square'
							? 'bg-primary-600 text-neutral-100'
							: 'bg-neutral-800 text-neutral-300 hover:bg-neutral-700'}"
						onclick={() => setAspectMode('square')}
					>
						1:1
					</button>
					<button
						type="button"
						class="min-h-touch rounded-lg px-2 py-2 text-caption transition-colors {aspectMode ===
						'wide'
							? 'bg-primary-600 text-neutral-100'
							: 'bg-neutral-800 text-neutral-300 hover:bg-neutral-700'}"
						onclick={() => setAspectMode('wide')}
					>
						16:9
					</button>
					<button
						type="button"
						class="min-h-touch rounded-lg px-2 py-2 text-caption transition-colors {aspectMode ===
						'free'
							? 'bg-primary-600 text-neutral-100'
							: 'bg-neutral-800 text-neutral-300 hover:bg-neutral-700'}"
						onclick={() => setAspectMode('free')}
					>
						Free
					</button>
				</div>
				{#if aspectMode === 'free'}
					<label
						for="captureAspectSlider"
						class="mb-2 mt-4 block text-caption font-medium text-neutral-300"
					>
						Shape Ratio
					</label>
					<input
						id="captureAspectSlider"
						type="range"
						min="0.5"
						max="2"
						step="0.01"
						value={freeAspectRatio}
						oninput={handleAspectSlider}
						class="slider-primary h-2 w-full cursor-pointer rounded-lg bg-neutral-800"
					/>
				{/if}
			</div>

			<div>
				<label
					for="captureZoomSlider"
					class="mb-2 flex items-center gap-1.5 text-caption font-medium text-neutral-300"
				>
					<Search class="text-primary-400" size={16} strokeWidth={1.5} />
					Zoom
				</label>
				<input
					id="captureZoomSlider"
					type="range"
					min="0"
					max="1"
					step="0.005"
					value={zoomSliderValue}
					oninput={handleZoomSlider}
					class="slider-primary h-2 w-full cursor-pointer rounded-lg bg-neutral-800"
				/>
			</div>

			<div>
				<label
					for="captureRotationSlider"
					class="mb-2 flex items-center gap-1.5 text-caption font-medium text-neutral-300"
				>
					<RotateCcw class="text-primary-400" size={16} strokeWidth={1.5} />
					Rotation
				</label>
				<div class="flex items-center gap-2">
					<button
						type="button"
						class="flex min-h-touch min-w-touch flex-shrink-0 items-center justify-center rounded-lg bg-neutral-800 p-2 text-neutral-400 transition-colors hover:bg-neutral-700 hover:text-neutral-100"
						onclick={rotateLeft90}
						aria-label="Rotate 90 degrees left"
						title="-90 degrees"
					>
						<RotateCcw size={20} strokeWidth={1.5} />
					</button>
					<input
						id="captureRotationSlider"
						type="range"
						min={MIN_ROTATION}
						max={MAX_ROTATION}
						step="1"
						value={rotation}
						oninput={handleRotationSlider}
						class="slider-primary h-2 flex-1 cursor-pointer rounded-lg bg-neutral-800"
					/>
					<button
						type="button"
						class="flex min-h-touch min-w-touch flex-shrink-0 items-center justify-center rounded-lg bg-neutral-800 p-2 text-neutral-400 transition-colors hover:bg-neutral-700 hover:text-neutral-100"
						onclick={rotateRight90}
						aria-label="Rotate 90 degrees right"
						title="+90 degrees"
					>
						<RotateCw size={20} strokeWidth={1.5} />
					</button>
				</div>
			</div>

			<div class="flex justify-center">
				<button
					type="button"
					class="flex min-h-touch items-center gap-2 rounded-lg bg-neutral-800 px-4 py-2 text-body-sm text-neutral-300 transition-colors hover:bg-neutral-700 hover:text-neutral-100"
					onclick={applyAutoSuggestion}
				>
					<Sparkles size={16} strokeWidth={1.5} />
					<span>Reset to Auto Crop</span>
				</button>
			</div>
		</div>

		<div class="flex gap-3 border-t border-neutral-700 p-4">
			<Button variant="secondary" onclick={onClose} disabled={isSaving}>Cancel</Button>
			<Button variant="primary" onclick={saveCrop} disabled={isSaving || !loadedImage}>
				<Check size={16} strokeWidth={1.5} />
				<span>{isSaving ? 'Saving...' : 'Use Cropped Photo'}</span>
			</Button>
		</div>
	</div>
</div>
