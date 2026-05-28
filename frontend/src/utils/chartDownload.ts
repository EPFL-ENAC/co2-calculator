interface EChartInstance {
  getDataURL(opts?: {
    type?: 'png' | 'svg' | 'jpeg';
    pixelRatio?: number;
    backgroundColor?: string;
  }): string;
}

function triggerPngDownload(url: string, filename: string): void {
  const link = document.createElement('a');
  link.href = url;
  link.download = filename.endsWith('.png') ? filename : `${filename}.png`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}

function pngFilename(base: string): string {
  return `${base}-${new Date().toISOString().replace(/[:.]/g, '-')}.png`;
}

export async function downloadEchartAsPng(
  chart: EChartInstance | null | undefined,
  filenameBase: string,
): Promise<void> {
  if (!chart) return;
  try {
    await new Promise<void>((resolve) => setTimeout(resolve, 200));
    const url = chart.getDataURL({
      type: 'png',
      pixelRatio: 2,
      backgroundColor: '#fff',
    });
    triggerPngDownload(url, pngFilename(filenameBase));
  } catch (error) {
    console.error('Error downloading chart:', error);
  }
}

function loadImage(url: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = reject;
    img.src = url;
  });
}

export interface CompositeColumn {
  title: string;
  charts: Array<EChartInstance | null | undefined>;
}

/** Stitches multiple ECharts instances side-by-side into one PNG download. */
export async function downloadCompositeChartAsPng(
  columns: CompositeColumn[],
  filenameBase: string,
  colWidth = 400,
  chartHeight = 300,
  titleHeight = 40,
): Promise<void> {
  const visibleCols = columns.filter((c) => c.charts.some(Boolean));
  if (visibleCols.length === 0) return;

  try {
    await new Promise<void>((resolve) => setTimeout(resolve, 200));

    const maxRows = Math.max(
      ...visibleCols.map((c) => c.charts.filter(Boolean).length),
    );
    const canvas = document.createElement('canvas');
    canvas.width = colWidth * visibleCols.length;
    canvas.height = titleHeight + chartHeight * maxRows;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    ctx.fillStyle = '#ffffff';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    for (let i = 0; i < visibleCols.length; i++) {
      const col = visibleCols[i];
      const x = i * colWidth;

      ctx.font = 'bold 14px Arial, sans-serif';
      ctx.fillStyle = '#333333';
      ctx.textAlign = 'center';
      ctx.fillText(col.title, x + colWidth / 2, 24);

      let rowIndex = 0;
      for (const chart of col.charts) {
        if (!chart) continue;
        const url = chart.getDataURL({
          type: 'png',
          pixelRatio: 2,
          backgroundColor: '#fff',
        });
        const img = await loadImage(url);
        ctx.drawImage(
          img,
          x,
          titleHeight + rowIndex * chartHeight,
          colWidth,
          chartHeight,
        );
        rowIndex++;
      }

      if (i < visibleCols.length - 1) {
        ctx.strokeStyle = 'rgba(0,0,0,0.12)';
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(x + colWidth, 0);
        ctx.lineTo(x + colWidth, canvas.height);
        ctx.stroke();
      }
    }

    triggerPngDownload(
      canvas.toDataURL('image/png'),
      pngFilename(filenameBase),
    );
  } catch (error) {
    console.error('Error downloading composite chart:', error);
  }
}
