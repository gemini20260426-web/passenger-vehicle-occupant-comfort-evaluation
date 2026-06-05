#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
报表增强模块 (R1-R4: 报告模板化+图表嵌入+多语言+版本管理)

提供:
- R1: 报告模板化 (Jinja2 HTML模板)
- R2: 图表嵌入 (Base64图片内嵌)
- R3: 多语言支持 (中/英双语)
- R4: 报告版本管理 (递增版本号 + 变更diff)
"""

import logging
import os
import json
import base64
import hashlib
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass, field
from io import BytesIO

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# R3: 多语言支持
# ══════════════════════════════════════════════════════════════════════════════

TRANSLATIONS = {
    'zh': {
        'report_title': '座椅舒适性评测报告',
        'summary': '汇总信息',
        'metrics': '指标汇总',
        'anomalies': '异常标注',
        'recommendations': '诊断建议',
        'total_metrics': '总指标数',
        'anomaly_count': '异常数',
        'risk_level': '风险等级',
        'generated_at': '生成时间',
        'metric_id': '指标ID',
        'value': '数值',
        'unit': '单位',
        'grade': '评级',
        'location': '位置',
        'severity': '严重度',
        'direction': '方向',
        'suggestion': '建议',
        'baseline': '基线值',
        'current': '当前值',
        'change_pct': '变化%',
        'improved': '改善',
        'degraded': '退化',
        'stable': '稳定',
        'significant': '显著',
        'moderate': '明显',
        'negligible': '轻微',
        'critical': '严重',
        'warning': '警告',
        'notice': '注意',
        'normal': '正常',
        'export_pdf': '导出PDF',
        'export_markdown': '导出Markdown',
        'export_excel': '导出Excel',
        'version': '版本',
        'previous_version': '上一版本',
        'changes': '变更内容',
        'no_changes': '无变更',
    },
    'en': {
        'report_title': 'Seat Comfort Evaluation Report',
        'summary': 'Summary',
        'metrics': 'Metrics',
        'anomalies': 'Anomalies',
        'recommendations': 'Recommendations',
        'total_metrics': 'Total Metrics',
        'anomaly_count': 'Anomaly Count',
        'risk_level': 'Risk Level',
        'generated_at': 'Generated At',
        'metric_id': 'Metric ID',
        'value': 'Value',
        'unit': 'Unit',
        'grade': 'Grade',
        'location': 'Location',
        'severity': 'Severity',
        'direction': 'Direction',
        'suggestion': 'Suggestion',
        'baseline': 'Baseline',
        'current': 'Current',
        'change_pct': 'Change %',
        'improved': 'Improved',
        'degraded': 'Degraded',
        'stable': 'Stable',
        'significant': 'Significant',
        'moderate': 'Moderate',
        'negligible': 'Negligible',
        'critical': 'Critical',
        'warning': 'Warning',
        'notice': 'Notice',
        'normal': 'Normal',
        'export_pdf': 'Export PDF',
        'export_markdown': 'Export Markdown',
        'export_excel': 'Export Excel',
        'version': 'Version',
        'previous_version': 'Previous Version',
        'changes': 'Changes',
        'no_changes': 'No changes',
    }
}


class I18nManager:
    """多语言管理器 (R3)"""

    def __init__(self, language: str = 'zh'):
        self._language = language
        self._translations = TRANSLATIONS

    def set_language(self, language: str):
        if language in self._translations:
            self._language = language

    def t(self, key: str, default: str = '') -> str:
        """翻译键值"""
        return self._translations.get(self._language, {}).get(key, default or key)

    def get_language(self) -> str:
        return self._language

    @property
    def available_languages(self) -> List[str]:
        return list(self._translations.keys())


# ══════════════════════════════════════════════════════════════════════════════
# R1: 报告模板化 + R2: 图表嵌入
# ══════════════════════════════════════════════════════════════════════════════

REPORT_TEMPLATE_HTML = '''<!DOCTYPE html>
<html lang="{{ lang }}">
<head>
<meta charset="UTF-8">
<title>{{ title }}</title>
<style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif; 
           background: #1a1a2e; color: #e0e0e0; margin: 20px; line-height: 1.6; }
    .header { text-align: center; padding: 20px; background: linear-gradient(135deg, #16213e, #1a1a2e); 
              border-radius: 8px; margin-bottom: 20px; }
    .header h1 { color: #2196F3; margin-bottom: 10px; }
    .header .meta { color: #888; font-size: 12px; }
    .section { background: #16213e; border: 1px solid #333; border-radius: 8px; 
               padding: 15px; margin: 10px 0; }
    .section h2 { color: #4CAF50; font-size: 16px; border-bottom: 1px solid #333; 
                 padding-bottom: 8px; margin-bottom: 12px; }
    .summary-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); 
                    gap: 10px; }
    .summary-card { background: #1a1a2e; border: 1px solid #333; border-radius: 6px; 
                    padding: 12px; text-align: center; }
    .summary-card .value { font-size: 24px; font-weight: bold; }
    .summary-card .label { color: #888; font-size: 11px; margin-top: 4px; }
    .risk-critical { color: #F44336; }
    .risk-high { color: #FF9800; }
    .risk-medium { color: #FFC107; }
    .risk-low { color: #8BC34A; }
    .risk-normal { color: #4CAF50; }
    table { width: 100%; border-collapse: collapse; font-size: 12px; }
    th { background: #0d1117; color: #aaa; padding: 8px; text-align: left; 
         font-weight: 600; border-bottom: 2px solid #333; }
    td { padding: 6px 8px; border-bottom: 1px solid #2a2a4e; }
    tr:hover { background: #2a2a4e; }
    .severity-critical { background: #4a1a1a !important; }
    .severity-warning { background: #3a3a1a !important; }
    .chart-container { text-align: center; margin: 15px 0; }
    .chart-container img { max-width: 100%; border-radius: 6px; }
    .diff-added { color: #4CAF50; }
    .diff-removed { color: #F44336; }
    .diff-changed { color: #FFC107; }
    .footer { text-align: center; color: #666; font-size: 11px; margin-top: 30px; 
              padding-top: 15px; border-top: 1px solid #333; }
    .version-info { background: #0d1117; padding: 8px 12px; border-radius: 4px; 
                    font-size: 11px; color: #888; margin-bottom: 15px; }
</style>
</head>
<body>
<div class="header">
    <h1>{{ title }}</h1>
    <div class="meta">{{ generated_at }} | {{ version_label }}</div>
</div>

<div class="version-info">
    {{ version_label }}: {{ version }} | {{ previous_version_label }}: {{ previous_version }}
</div>

<div class="section">
    <h2>{{ summary_label }}</h2>
    <div class="summary-grid">
        <div class="summary-card">
            <div class="value" style="color: #2196F3;">{{ total_metrics }}</div>
            <div class="label">{{ total_metrics_label }}</div>
        </div>
        <div class="summary-card">
            <div class="value" style="color: {{ risk_color }};">{{ anomaly_count }}</div>
            <div class="label">{{ anomaly_count_label }}</div>
        </div>
        <div class="summary-card">
            <div class="value risk-{{ risk_level }}">{{ risk_level }}</div>
            <div class="label">{{ risk_level_label }}</div>
        </div>
    </div>
</div>

{% if chart_images %}
<div class="section">
    <h2>图表</h2>
    {% for chart in chart_images %}
    <div class="chart-container">
        <img src="data:image/png;base64,{{ chart.data }}" alt="{{ chart.title }}">
        <p style="color: #888; font-size: 11px;">{{ chart.title }}</p>
    </div>
    {% endfor %}
</div>
{% endif %}

<div class="section">
    <h2>{{ metrics_label }}</h2>
    <table>
        <tr>
            <th>{{ metric_id_label }}</th>
            <th>{{ value_label }}</th>
            <th>{{ unit_label }}</th>
            <th>{{ location_label }}</th>
            <th>{{ grade_label }}</th>
        </tr>
        {{ metric_rows }}
    </table>
</div>

{% if anomaly_rows %}
<div class="section">
    <h2>{{ anomalies_label }}</h2>
    <table>
        <tr>
            <th>{{ metric_id_label }}</th>
            <th>{{ value_label }}</th>
            <th>{{ deviation_label }}</th>
            <th>{{ severity_label }}</th>
            <th>{{ suggestion_label }}</th>
        </tr>
        {{ anomaly_rows }}
    </table>
</div>
{% endif %}

{% if recommendations %}
<div class="section">
    <h2>{{ recommendations_label }}</h2>
    <ul style="padding-left: 20px;">
        {% for rec in recommendations %}
        <li style="margin: 6px 0;">{{ rec }}</li>
        {% endfor %}
    </ul>
</div>
{% endif %}

{% if version_diff %}
<div class="section">
    <h2>{{ changes_label }}</h2>
    <pre style="color: #e0e0e0; font-size: 12px;">{{ version_diff }}</pre>
</div>
{% endif %}

<div class="footer">
    {{ footer_text }} | {{ generated_at }}
</div>
</body>
</html>'''

REPORT_TEMPLATE_MD = '''# {{ title }}

**{{ generated_at }}** | {{ version_label }}: {{ version }}

---

## {{ summary_label }}

| {{ total_metrics_label }} | {{ anomaly_count_label }} | {{ risk_level_label }} |
|:---:|:---:|:---:|
| {{ total_metrics }} | {{ anomaly_count }} | {{ risk_level }} |

---

## {{ metrics_label }}

| {{ metric_id_label }} | {{ value_label }} | {{ unit_label }} | {{ grade_label }} |
|:---|:---:|:---:|:---:|
{{ metric_rows }}

---

{% if anomaly_rows %}
## {{ anomalies_label }}

| {{ metric_id_label }} | {{ value_label }} | {{ deviation_label }} | {{ severity_label }} | {{ suggestion_label }} |
|:---|:---:|:---:|:---:|:---|
{{ anomaly_rows }}

---
{% endif %}

{% if recommendations %}
## {{ recommendations_label }}

{% for rec in recommendations %}
- {{ rec }}
{% endfor %}

---
{% endif %}

{% if version_diff %}
## {{ changes_label }}

```
{{ version_diff }}
```
{% endif %}

*{{ footer_text }} | {{ generated_at }}*
'''


class TemplateRenderer:
    """模板渲染器 (R1: 报告模板化)"""

    def __init__(self, language: str = 'zh'):
        self.i18n = I18nManager(language)
        self._charts: List[Dict[str, str]] = []  # [{title, data(base64)}]

    def set_language(self, language: str):
        self.i18n.set_language(language)

    def embed_chart(self, figure_data: bytes, title: str, format: str = 'png'):
        """嵌入图表 (R2: 图表嵌入)

        Args:
            figure_data: 图表二进制数据
            title: 图表标题
            format: 图片格式
        """
        b64_data = base64.b64encode(figure_data).decode('utf-8')
        self._charts.append({
            'title': title,
            'data': b64_data,
            'format': format
        })

    def render_html(self, data: Dict[str, Any], version_info: Dict[str, Any] = None) -> str:
        """渲染HTML报告"""
        t = self.i18n.t
        metrics = data.get('metrics', {})
        anomalies = data.get('anomalies', [])
        recommendations = data.get('recommendations', [])
        summary = data.get('summary', {})
        version_info = version_info or {}

        # 风险颜色
        risk_colors = {
            'critical': '#F44336', 'high': '#FF9800', 'medium': '#FFC107',
            'low': '#8BC34A', 'normal': '#4CAF50'
        }

        # 指标表格行
        metric_rows = ''
        for mid, info in list(metrics.items())[:50]:
            metric_rows += f'''
            <tr>
                <td>{mid}</td>
                <td>{info.get('value', 0):.3f}</td>
                <td>{info.get('unit', '')}</td>
                <td>{info.get('location', '')}</td>
                <td>{info.get('grade', '-')}</td>
            </tr>'''

        # 异常表格行
        anomaly_rows = ''
        for a in anomalies:
            anomaly_rows += f'''
            <tr class="severity-{a.get('severity', 'notice')}">
                <td>{a.get('metric_id', '')}</td>
                <td>{a.get('value', 0):.3f}</td>
                <td>{a.get('deviation_sigma', 0):.1f}σ</td>
                <td>{t(a.get('severity', 'notice'))}</td>
                <td>{a.get('suggestion', '')}</td>
            </tr>'''

        # 版本diff
        version_diff = ''
        if version_info.get('changes'):
            for change in version_info['changes']:
                if change['type'] == 'added':
                    version_diff += f'<div class="diff-added">+ {change["metric_id"]}: {change["value"]}</div>'
                elif change['type'] == 'removed':
                    version_diff += f'<div class="diff-removed">- {change["metric_id"]}: {change["value"]}</div>'
                elif change['type'] == 'changed':
                    version_diff += f'<div class="diff-changed">~ {change["metric_id"]}: {change["old_value"]} → {change["new_value"]}</div>'

        risk_level = summary.get('risk_level', 'normal')

        # 简单模板替换
        html = REPORT_TEMPLATE_HTML
        html = html.replace('{{ lang }}', self.i18n.get_language())
        html = html.replace('{{ title }}', t('report_title'))
        html = html.replace('{{ generated_at }}', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        html = html.replace('{{ version_label }}', t('version'))
        html = html.replace('{{ version }}', str(version_info.get('version', 1)))
        html = html.replace('{{ previous_version_label }}', t('previous_version'))
        html = html.replace('{{ previous_version }}', str(version_info.get('previous_version', 'N/A')))
        html = html.replace('{{ summary_label }}', t('summary'))
        html = html.replace('{{ total_metrics }}', str(summary.get('total_metrics', 0)))
        html = html.replace('{{ total_metrics_label }}', t('total_metrics'))
        html = html.replace('{{ anomaly_count }}', str(summary.get('anomaly_count', 0)))
        html = html.replace('{{ anomaly_count_label }}', t('anomaly_count'))
        html = html.replace('{{ risk_level }}', risk_level)
        html = html.replace('{{ risk_color }}', risk_colors.get(risk_level, '#4CAF50'))
        html = html.replace('{{ risk_level_label }}', t('risk_level'))
        html = html.replace('{{ metrics_label }}', t('metrics'))
        html = html.replace('{{ metric_id_label }}', t('metric_id'))
        html = html.replace('{{ value_label }}', t('value'))
        html = html.replace('{{ unit_label }}', t('unit'))
        html = html.replace('{{ location_label }}', t('location'))
        html = html.replace('{{ grade_label }}', t('grade'))
        html = html.replace('{{ metric_rows }}', metric_rows)
        html = html.replace('{{ anomalies_label }}', t('anomalies'))
        html = html.replace('{{ anomaly_rows }}', anomaly_rows)
        html = html.replace('{{ deviation_label }}', '偏离')
        html = html.replace('{{ severity_label }}', t('severity'))
        html = html.replace('{{ suggestion_label }}', t('suggestion'))
        html = html.replace('{{ recommendations_label }}', t('recommendations'))
        html = html.replace('{{ changes_label }}', t('changes'))
        html = html.replace('{{ version_diff }}', version_diff or t('no_changes'))
        html = html.replace('{{ footer_text }}', '全量统计分析模块自动生成')
        html = html.replace('{{ no_changes }}', t('no_changes'))

        # 图表嵌入 (R2)
        if self._charts:
            chart_html = ''
            for chart in self._charts:
                chart_html += f'''
            <div class="chart-container">
                <img src="data:image/{chart['format']};base64,{chart['data']}" alt="{chart['title']}">
                <p style="color: #888; font-size: 11px;">{chart['title']}</p>
            </div>'''
            html = html.replace('{% if chart_images %}', '')
            html = html.replace('{% for chart in chart_images %}', '')
            html = html.replace('{% endfor %}', '')
            html = html.replace('{% endif %}', '')
            html = html.replace('{{ chart.title }}', '')
            html = html.replace('{{ chart.data }}', '')
            html = html.replace('<div class="chart-container">', chart_html, 1)

        return html

    def render_markdown(self, data: Dict[str, Any], version_info: Dict[str, Any] = None) -> str:
        """渲染Markdown报告"""
        t = self.i18n.t
        metrics = data.get('metrics', {})
        anomalies = data.get('anomalies', [])
        recommendations = data.get('recommendations', [])
        summary = data.get('summary', {})
        version_info = version_info or {}

        # 指标表格行
        metric_rows = ''
        for mid, info in list(metrics.items())[:50]:
            metric_rows += f"| {mid} | {info.get('value', 0):.3f} | {info.get('unit', '')} | {info.get('grade', '-')} |\n"

        # 异常表格行
        anomaly_rows = ''
        for a in anomalies:
            anomaly_rows += f"| {a.get('metric_id', '')} | {a.get('value', 0):.3f} | {a.get('deviation_sigma', 0):.1f}σ | {t(a.get('severity', 'notice'))} | {a.get('suggestion', '')} |\n"

        md = REPORT_TEMPLATE_MD
        md = md.replace('{{ title }}', t('report_title'))
        md = md.replace('{{ generated_at }}', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        md = md.replace('{{ version_label }}', t('version'))
        md = md.replace('{{ version }}', str(version_info.get('version', 1)))
        md = md.replace('{{ summary_label }}', t('summary'))
        md = md.replace('{{ total_metrics }}', str(summary.get('total_metrics', 0)))
        md = md.replace('{{ total_metrics_label }}', t('total_metrics'))
        md = md.replace('{{ anomaly_count }}', str(summary.get('anomaly_count', 0)))
        md = md.replace('{{ anomaly_count_label }}', t('anomaly_count'))
        md = md.replace('{{ risk_level }}', summary.get('risk_level', 'normal'))
        md = md.replace('{{ risk_level_label }}', t('risk_level'))
        md = md.replace('{{ metrics_label }}', t('metrics'))
        md = md.replace('{{ metric_id_label }}', t('metric_id'))
        md = md.replace('{{ value_label }}', t('value'))
        md = md.replace('{{ unit_label }}', t('unit'))
        md = md.replace('{{ grade_label }}', t('grade'))
        md = md.replace('{{ metric_rows }}', metric_rows)
        md = md.replace('{{ anomalies_label }}', t('anomalies'))
        md = md.replace('{{ anomaly_rows }}', anomaly_rows)
        md = md.replace('{{ deviation_label }}', '偏离')
        md = md.replace('{{ severity_label }}', t('severity'))
        md = md.replace('{{ suggestion_label }}', t('suggestion'))
        md = md.replace('{{ recommendations_label }}', t('recommendations'))
        md = md.replace('{{ changes_label }}', t('changes'))
        md = md.replace('{{ version_diff }}', t('no_changes'))
        md = md.replace('{{ footer_text }}', '全量统计分析模块自动生成')

        # 建议列表
        rec_list = ''
        for rec in recommendations:
            rec_list += f'- {rec}\n'
        md = md.replace('{% for rec in recommendations %}\n- {{ rec }}\n{% endfor %}', rec_list)

        return md

    def clear_charts(self):
        self._charts.clear()


# ══════════════════════════════════════════════════════════════════════════════
# R4: 报告版本管理
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class ReportVersion:
    """报告版本"""
    version: int
    timestamp: float
    metrics_hash: str
    metrics: Dict[str, float]
    summary: Dict[str, Any]
    changes: List[Dict[str, Any]] = field(default_factory=list)


class ReportVersionManager:
    """报告版本管理器 (R4)"""

    def __init__(self, storage_path: str = ''):
        self.storage_path = storage_path or os.path.join(os.getcwd(), 'report_versions')
        os.makedirs(self.storage_path, exist_ok=True)
        self._versions: List[ReportVersion] = []
        self._load_versions()

    def save_version(self, metrics: Dict[str, float],
                     summary: Dict[str, Any] = None) -> ReportVersion:
        """保存新版本，自动递增版本号

        Returns:
            ReportVersion: 新版本
        """
        # 计算指标哈希
        metrics_hash = self._compute_hash(metrics)

        # 检查是否与上一版本相同
        if self._versions:
            last = self._versions[-1]
            if last.metrics_hash == metrics_hash:
                logger.debug("指标未变化，跳过版本保存")
                return last

        # 新版本号
        new_version = len(self._versions) + 1

        # 计算变更
        changes = []
        if self._versions:
            changes = self._compute_diff(self._versions[-1].metrics, metrics)

        rv = ReportVersion(
            version=new_version,
            timestamp=datetime.now().timestamp(),
            metrics_hash=metrics_hash,
            metrics=dict(metrics),
            summary=summary or {},
            changes=changes
        )

        self._versions.append(rv)
        self._save_versions()

        logger.info(f"报告版本已保存: v{new_version} ({len(changes)} changes)")
        return rv

    def get_latest_version(self) -> Optional[ReportVersion]:
        """获取最新版本"""
        return self._versions[-1] if self._versions else None

    def get_version(self, version: int) -> Optional[ReportVersion]:
        """获取指定版本"""
        for v in self._versions:
            if v.version == version:
                return v
        return None

    def get_version_info(self, version: int = -1) -> Dict[str, Any]:
        """获取版本信息"""
        if version < 0 and self._versions:
            v = self._versions[version]
        elif version > 0:
            v = self.get_version(version)
        else:
            return {'version': 0, 'previous_version': 'N/A', 'changes': []}

        if v is None:
            return {'version': 0, 'previous_version': 'N/A', 'changes': []}

        prev_version = self._versions[v.version - 2].version if v.version > 1 else 'N/A'

        return {
            'version': v.version,
            'previous_version': prev_version,
            'timestamp': v.timestamp,
            'changes': v.changes,
            'summary': v.summary
        }

    def get_all_versions(self) -> List[Dict[str, Any]]:
        """获取所有版本列表"""
        return [
            {
                'version': v.version,
                'timestamp': v.timestamp,
                'metrics_count': len(v.metrics),
                'changes_count': len(v.changes)
            }
            for v in self._versions
        ]

    def _compute_diff(self, old_metrics: Dict[str, float],
                      new_metrics: Dict[str, float]) -> List[Dict[str, Any]]:
        """计算两个版本之间的差异"""
        changes = []

        all_keys = set(old_metrics.keys()) | set(new_metrics.keys())

        for key in sorted(all_keys):
            old_val = old_metrics.get(key)
            new_val = new_metrics.get(key)

            if old_val is None and new_val is not None:
                changes.append({'type': 'added', 'metric_id': key, 'value': new_val})
            elif old_val is not None and new_val is None:
                changes.append({'type': 'removed', 'metric_id': key, 'value': old_val})
            elif abs(old_val - new_val) > 1e-6:
                changes.append({
                    'type': 'changed',
                    'metric_id': key,
                    'old_value': old_val,
                    'new_value': new_val,
                    'change_pct': round((new_val - old_val) / abs(old_val) * 100, 2) if abs(old_val) > 1e-6 else 0
                })

        return changes

    @staticmethod
    def _compute_hash(metrics: Dict[str, float]) -> str:
        """计算指标哈希"""
        sorted_items = sorted(metrics.items())
        data = json.dumps(sorted_items, sort_keys=True).encode('utf-8')
        return hashlib.md5(data).hexdigest()

    def _save_versions(self):
        """保存版本到磁盘"""
        filepath = os.path.join(self.storage_path, 'versions.json')
        data = [
            {
                'version': v.version,
                'timestamp': v.timestamp,
                'metrics_hash': v.metrics_hash,
                'metrics': v.metrics,
                'summary': v.summary,
                'changes': v.changes
            }
            for v in self._versions
        ]
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _load_versions(self):
        """从磁盘加载版本"""
        filepath = os.path.join(self.storage_path, 'versions.json')
        if not os.path.exists(filepath):
            return

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)

            self._versions = [
                ReportVersion(
                    version=d['version'],
                    timestamp=d['timestamp'],
                    metrics_hash=d['metrics_hash'],
                    metrics=d['metrics'],
                    summary=d.get('summary', {}),
                    changes=d.get('changes', [])
                )
                for d in data
            ]
            logger.info(f"已加载 {len(self._versions)} 个报告版本")
        except Exception as e:
            logger.error(f"加载版本失败: {e}")

    def clear(self):
        """清空版本历史"""
        self._versions.clear()
        filepath = os.path.join(self.storage_path, 'versions.json')
        if os.path.exists(filepath):
            os.remove(filepath)
        logger.info("版本历史已清空")