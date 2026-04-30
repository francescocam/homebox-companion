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
		onSave: (result: CropEditorResult) => void | Promise<void>;
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
	let cropRect = $state<CropRect>({ x: 0, y: 0, width: 0, height: 0 });

	type ResizeHandle = 'n' | 's' | 'e' | 'w' | 'nw' | 'ne' | 'sw' | 'se' | null;
	let activeResizeHandle = $state<ResizeHandle>(null);

	let lastX = 0;
	let lastY = 0;
	let lastTouchDistance = 0;
	let lastTouchAngle = 0;

	const MAX_SCALE = 5;
	const MIN_ROTATION = -180;
	const MAX_ROTATION = 180;
	const MIN_CROP_SIZE_RATIO = 0.35;
	const CROP_HANDLE_HIT_SIZE = 34;
	const CROP_BORDER_HIT_SIZE = 20;
	let zoomSliderValue = $derived(scaleToSlider(scale));

	onMount(() => {
		const viewportWidth = window.innerWidth;
		canvasSize =
			viewportWidth >= 640 ? Math.min(520, viewportWidth - 96) : Math.min(440, viewportWidth - 32);
		const initialSize = Math.round(canvasSize * 0.86);
		cropRect = {
			x: Math.round((canvasSize - initialSize) / 2),
			y: Math.round((canvasSize - initialSize) / 2),
			width: initialSize,
			height: initialSize,
		};

		requestAnimationFrame(async () => {
			ctx = canvas.getContext('2d');
			try {
				loadedImage = await loadImageElement(dataUrl);
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

	function getResizeHandle(point: { x: number; y: number }): ResizeHandle {
		const hit = CROP_HANDLE_HIT_SIZE;
		const borderHit = CROP_BORDER_HIT_SIZE;

		const nearLeft = Math.abs(point.x - cropRect.x) <= hit;
		const nearRight = Math.abs(point.x - (cropRect.x + cropRect.width)) <= hit;
		const nearTop = Math.abs(point.y - cropRect.y) <= hit;
		const nearBottom = Math.abs(point.y - (cropRect.y + cropRect.height)) <= hit;

		if (nearTop && nearLeft) return 'nw';
		if (nearTop && nearRight) return 'ne';
		if (nearBottom && nearLeft) return 'sw';
		if (nearBottom && nearRight) return 'se';

		const withinX =
			point.x >= cropRect.x - borderHit && point.x <= cropRect.x + cropRect.width + borderHit;
		const withinY =
			point.y >= cropRect.y - borderHit && point.y <= cropRect.y + cropRect.height + borderHit;

		if (withinY && Math.abs(point.x - cropRect.x) <= borderHit) return 'w';
		if (withinY && Math.abs(point.x - (cropRect.x + cropRect.width)) <= borderHit) return 'e';
		if (withinX && Math.abs(point.y - cropRect.y) <= borderHit) return 'n';
		if (withinX && Math.abs(point.y - (cropRect.y + cropRect.height)) <= borderHit) return 's';

		return null;
	}

	function getCursorForHandle(handle: ResizeHandle): string {
		if (!handle) return 'default';
		switch (handle) {
			case 'nw':
			case 'se':
				return 'nwse-resize';
			case 'ne':
			case 'sw':
				return 'nesw-resize';
			case 'n':
			case 's':
				return 'ns-resize';
			case 'e':
			case 'w':
				return 'ew-resize';
			default:
				return 'default';
		}
	}

	function applyResize(dx: number, dy: number) {
		if (!activeResizeHandle) return;
		let { x, y, width, height } = cropRect;
		const minSize = canvasSize * 0.25;

		if (activeResizeHandle.includes('w')) {
			const newWidth = Math.max(minSize, width - dx);
			const allowedDx = width - newWidth;
			const newX = Math.max(0, x + allowedDx);
			width = width + (x - newX);
			x = newX;
		}
		if (activeResizeHandle.includes('e')) {
			width = Math.min(canvasSize - x, Math.max(minSize, width + dx));
		}
		if (activeResizeHandle.includes('n')) {
			const newHeight = Math.max(minSize, height - dy);
			const allowedDy = height - newHeight;
			const newY = Math.max(0, y + allowedDy);
			height = height + (y - newY);
			y = newY;
		}
		if (activeResizeHandle.includes('s')) {
			height = Math.min(canvasSize - y, Math.max(minSize, height + dy));
		}

		cropRect = { x, y, width, height };
		updateMinimumScale();
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

	function moveCropBy(dx: number, dy: number) {
		let { x, y, width, height } = cropRect;
		x = clamp(x + dx, 0, canvasSize - width);
		y = clamp(y + dy, 0, canvasSize - height);
		cropRect = { x, y, width, height };
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

		const energyData = new Float32Array(sampleCanvas.width * sampleCanvas.height);
		let totalEnergy = 0;

		for (let y = 1; y < sampleCanvas.height - 1; y++) {
			for (let x = 1; x < sampleCanvas.width - 1; x++) {
				const i = (y * sampleCanvas.width + x) * 4;
				const iRight = (y * sampleCanvas.width + (x + 1)) * 4;
				const iDown = ((y + 1) * sampleCanvas.width + x) * 4;

				const gx =
					Math.abs(data[i] - data[iRight]) +
					Math.abs(data[i + 1] - data[iRight + 1]) +
					Math.abs(data[i + 2] - data[iRight + 2]);
				const gy =
					Math.abs(data[i] - data[iDown]) +
					Math.abs(data[i + 1] - data[iDown + 1]) +
					Math.abs(data[i + 2] - data[iDown + 2]);
				const energy = gx + gy;

				energyData[y * sampleCanvas.width + x] = energy;
				totalEnergy += energy;
			}
		}

		if (totalEnergy === 0) return null;

		const rowSums = new Float32Array(sampleCanvas.height);
		const colSums = new Float32Array(sampleCanvas.width);

		for (let y = 0; y < sampleCanvas.height; y++) {
			for (let x = 0; x < sampleCanvas.width; x++) {
				const e = energyData[y * sampleCanvas.width + x];
				rowSums[y] += e;
				colSums[x] += e;
			}
		}

		const targetTrim = totalEnergy * 0.075;

		let minX = 0;
		let currentTrim = 0;
		while (minX < sampleCanvas.width && currentTrim + colSums[minX] < targetTrim) {
			currentTrim += colSums[minX];
			minX++;
		}

		let maxX = sampleCanvas.width - 1;
		currentTrim = 0;
		while (maxX > minX && currentTrim + colSums[maxX] < targetTrim) {
			currentTrim += colSums[maxX];
			maxX--;
		}

		let minY = 0;
		currentTrim = 0;
		while (minY < sampleCanvas.height && currentTrim + rowSums[minY] < targetTrim) {
			currentTrim += rowSums[minY];
			minY++;
		}

		let maxY = sampleCanvas.height - 1;
		currentTrim = 0;
		while (maxY > minY && currentTrim + rowSums[maxY] < targetTrim) {
			currentTrim += rowSums[maxY];
			maxY--;
		}

		const width = maxX - minX + 1;
		const height = maxY - minY + 1;

		const padX = Math.round(width * 0.1);
		const padY = Math.round(height * 0.1);
		minX = Math.max(0, minX - padX);
		minY = Math.max(0, minY - padY);
		maxX = Math.min(sampleCanvas.width - 1, maxX + padX);
		maxY = Math.min(sampleCanvas.height - 1, maxY + padY);

		const scaleX = image.width / sampleCanvas.width;
		const scaleY = image.height / sampleCanvas.height;
		return {
			x: minX * scaleX,
			y: minY * scaleY,
			width: (maxX - minX + 1) * scaleX,
			height: (maxY - minY + 1) * scaleY,
		};
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
		const handle = getResizeHandle(point);
		if (handle) {
			isResizingCrop = true;
			isMovingCrop = false;
			activeResizeHandle = handle;
			canvas.style.cursor = getCursorForHandle(handle);
			lastX = e.clientX;
			lastY = e.clientY;
		} else if (isInsideCrop(point)) {
			isMovingCrop = true;
			isResizingCrop = false;
			lastX = e.clientX;
			lastY = e.clientY;
			canvas.style.cursor = 'move';
		}
	}

	function handleMouseMove(e: MouseEvent) {
		const rect = canvas.getBoundingClientRect();
		const dx = ((e.clientX - lastX) / rect.width) * canvasSize;
		const dy = ((e.clientY - lastY) / rect.height) * canvasSize;

		if (isResizingCrop) {
			applyResize(dx, dy);
			lastX = e.clientX;
			lastY = e.clientY;
			return;
		}

		if (isMovingCrop) {
			moveCropBy(dx, dy);
			lastX = e.clientX;
			lastY = e.clientY;
			return;
		}

		const point = getCanvasPoint(e.clientX, e.clientY);
		const handle = getResizeHandle(point);
		canvas.style.cursor = handle
			? getCursorForHandle(handle)
			: isInsideCrop(point)
				? 'move'
				: 'default';
	}

	function handleMouseUp() {
		isResizingCrop = false;
		isMovingCrop = false;
		activeResizeHandle = null;
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
			const handle = getResizeHandle(point);
			if (handle) {
				isResizingCrop = true;
				isMovingCrop = false;
				activeResizeHandle = handle;
				lastX = e.touches[0].clientX;
				lastY = e.touches[0].clientY;
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
			activeResizeHandle = null;
			lastTouchDistance = getTouchDistance(e.touches);
			lastTouchAngle = getTouchAngle(e.touches);
		}
	}

	function handleTouchMove(e: TouchEvent) {
		e.preventDefault();
		const rect = canvas.getBoundingClientRect();

		if (e.touches.length === 1 && isResizingCrop) {
			const dx = ((e.touches[0].clientX - lastX) / rect.width) * canvasSize;
			const dy = ((e.touches[0].clientY - lastY) / rect.height) * canvasSize;
			applyResize(dx, dy);
			lastX = e.touches[0].clientX;
			lastY = e.touches[0].clientY;
		} else if (e.touches.length === 1 && isMovingCrop) {
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
			render();
		}
	}

	function handleTouchEnd(e: TouchEvent) {
		if (e.touches.length === 0) {
			isMovingCrop = false;
			isResizingCrop = false;
			activeResizeHandle = null;
		} else if (e.touches.length === 1) {
			isMovingCrop = false;
			isResizingCrop = false;
			activeResizeHandle = null;
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
				cropAspectRatio: cropRect.width / cropRect.height,
				cropCenterX: cropRect.x + cropRect.width / 2,
				cropCenterY: cropRect.y + cropRect.height / 2,
				edited: true,
			};
			const result = await exportCroppedImage({
				image: loadedImage,
				originalName: file.name,
				transform,
				cropRect,
				backgroundColor: CANVAS_COLORS.background,
			});
			await onSave(result);
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
				class="rounded-lg {isMovingCrop ? 'cursor-move' : ''}"
				style="touch-action: none; {isResizingCrop && activeResizeHandle
					? `cursor: ${getCursorForHandle(activeResizeHandle)};`
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
