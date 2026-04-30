# ruff: noqa: E501

with open('frontend/src/lib/components/CaptureCropEditor.svelte') as f:
    content = f.read()

# 1. State changes
content = content.replace('''	let cropSizeRatio = $state(0.86);
	let cropAspectRatio = $state(1);
	let cropCenterX = $state(170);
	let cropCenterY = $state(170);''', '''	let cropRect = $state<CropRect>({ x: 0, y: 0, width: 0, height: 0 });

	type ResizeHandle = 'n' | 's' | 'e' | 'w' | 'nw' | 'ne' | 'sw' | 'se' | null;
	let activeResizeHandle = $state<ResizeHandle>(null);''')

content = content.replace('''	const MAX_CROP_SIZE_RATIO = 0.92;
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
	});''', '''	const CROP_HANDLE_HIT_SIZE = 34;
	const CROP_BORDER_HIT_SIZE = 20;''')

content = content.replace('''		cropCenterX = canvasSize / 2;
		cropCenterY = canvasSize / 2;

		requestAnimationFrame(async () => {
			ctx = canvas.getContext('2d');
			try {
				loadedImage = await loadImageElement(dataUrl);
				cropAspectRatio = loadedImage.width / loadedImage.height;
				freeAspectRatio = cropAspectRatio;
				applyAutoSuggestion();''', '''		const initialSize = Math.round(canvasSize * 0.86);
		cropRect = {
			x: Math.round((canvasSize - initialSize) / 2),
			y: Math.round((canvasSize - initialSize) / 2),
			width: initialSize,
			height: initialSize
		};

		requestAnimationFrame(async () => {
			ctx = canvas.getContext('2d');
			try {
				loadedImage = await loadImageElement(dataUrl);
				applyAutoSuggestion();''')

content = content.replace('''		updateMinimumScale();
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
	}''', '''		const suggestedBounds = detectContentBounds(loadedImage);
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
	}''')

content = content.replace('''	function isNearCropHandle(point: { x: number; y: number }): boolean {
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
	}''', '''	function getResizeHandle(point: { x: number; y: number }): ResizeHandle {
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

		const withinX = point.x >= cropRect.x - borderHit && point.x <= cropRect.x + cropRect.width + borderHit;
		const withinY = point.y >= cropRect.y - borderHit && point.y <= cropRect.y + cropRect.height + borderHit;

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
	}''')

content = content.replace('''	function handleMouseDown(e: MouseEvent) {
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
	}''', '''	function handleMouseDown(e: MouseEvent) {
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
	}''')

content = content.replace('''	function handleTouchStart(e: TouchEvent) {
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
	}''', '''	function handleTouchStart(e: TouchEvent) {
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
	}''')

content = content.replace('''			const transform: CaptureImageTransform = {
				scale,
				rotation,
				offsetX,
				offsetY,
				cropAspectRatio,
				cropCenterX,
				cropCenterY,
				edited: true,
			};''', '''			const transform: CaptureImageTransform = {
				scale,
				rotation,
				offsetX,
				offsetY,
				cropAspectRatio: cropRect.width / cropRect.height,
				cropCenterX: cropRect.x + cropRect.width / 2,
				cropCenterY: cropRect.y + cropRect.height / 2,
				edited: true,
			};''')

# Now the UI changes
content = content.replace('''			<canvas
				bind:this={canvas}
				width={canvasSize}
				height={canvasSize}
				class="rounded-lg {isResizingCrop ? 'cursor-nwse-resize' : ''} {isMovingCrop
					? 'cursor-move'
					: ''}"
				onmousedown={handleMouseDown}''', '''			<canvas
				bind:this={canvas}
				width={canvasSize}
				height={canvasSize}
				class="rounded-lg {isMovingCrop ? 'cursor-move' : ''}"
				style="touch-action: none; {isResizingCrop && activeResizeHandle ? `cursor: ${getCursorForHandle(activeResizeHandle)};` : ''}"
				onmousedown={handleMouseDown}''')

# Remove sliders
to_remove = '''			<div>
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
			</div>'''

content = content.replace(to_remove, '')

with open('frontend/src/lib/components/CaptureCropEditor.svelte', 'w') as f:
    f.write(content)

print("Done")
