from dataclasses import asdict
from datetime import datetime, timezone
import json
from app.core.safe_output import SafeOutputWriter


def write_report(output_dir, tool_id, results):
    records = []
    for index, result in enumerate(results, 1):
        data = asdict(result)
        # Stable queue index rather than children's names or absolute input paths.
        data['source'] = f'文件 {index}'
        data['output'] = result.output.name if result.output else None
        records.append(data)
    payload = {'tool': tool_id, 'created_at': datetime.now(timezone.utc).isoformat(),
               'results': records}
    with SafeOutputWriter(output_dir / '处理报告.json') as writer:
        writer.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
        return writer.commit()
