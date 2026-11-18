# 轨检资料中心冻结汇总湖

监测班将设备计量登记为日批修订。仓管员冻结实际留存的工段汇总。明细到期后，值班员可以凭同一修订的留存补发月报账项，夜班按固定报告编号复核。

## 运行

需要 Python 3.11 和标准库自带的 SQLite 支持。在项目根目录执行：

```sh
python3 -B -m unittest discover -s tests -v
python3 -B demo.py
```

演示从 `samples/rail_day.json` 读取固定输入，在独立临时归档中操作。A、B、C 三段同属一组，各计 4、10、16 分。AB、AC、BC 三份留存分别为 14、20、26 分。到期后全线补报应为三行、三个非空金额、30 分。演示随后冻结更正并重开归档，按旧报告号核对原账。

## 公开 Python 接口

```python
from contextlib import closing
from intake.batches import stage
from intake.rows import SourceRow
from reports.archive import open_archive
from reports.publish import reissue_report
from reports.read import read
from retention.expiry import expire
from retention.seal import seal

with closing(open_archive('rail-lake.sqlite3')) as archive:
    revision = stage(archive, '2026-10-01', 'r1', [
        SourceRow('a1', 'A', '甲班', 4),
        SourceRow('b1', 'B', '甲班', 10),
        SourceRow('c1', 'C', '甲班', 16),
    ])
    directory = seal(archive, revision.key, [('A', 'B'), ('A', 'C'), ('B', 'C')])
    expire(archive, revision.key, '2026-10-08')
    report = reissue_report(archive, revision.key, {'C', 'B', 'A'})
    saved = read(archive, report.header.number)
```

示例中的日批、修订组合适用于首次登记。`stage` 接受 ISO `YYYY-MM-DD` 字符串或 `datetime.date`，以及可迭代的 `SourceRow`。修订标识、行标识、工段和班组是有效 UTF-8 的非空白字符串，不含 NUL，保留原文。金额是 Python `int` 或 `None`。行标识在同一修订内唯一。再次登记可编辑修订会替换整份源账。更正使用独立修订标识。`RevisionKey.from_parts` 可从已知日批和修订标识重新构造查询键。

`seal` 接受可编辑修订和非空覆盖清单。每份覆盖均为该修订已知工段的非空集合，允许重叠。工段及重复覆盖按集合语义规范化。返回的 `RollupRef` 可用 `retention.payload.load_rollup_payload` 检查留存班组统计。`intake.rows.iter_source_rows` 可在到期前核对该版源账，按行标识排序。冻结状态、工段清单、到期台账、目录和载荷一次提交。冻结后源账及留存固定。每份覆盖分别核算，空额计入总行数，显式零也计入非空金额数。冻结载荷保留整数金额累加值，全空班组的累加值为零。

`expire` 使用调用者给出的业务日期。归档留存期为日批日后七个自然日，冻结时写入台账。到期当天即可清理。返回 `ExpiryResult.EXPIRED` 或 `ExpiryResult.ALREADY_EXPIRED`。已清理的修订保持冻结，继续保留工段和汇总。清理范围由日批及修订共同限定。

`reissue_report` 接受指定冻结修订及非空目标工段集合。已知但留存证据不足的工段仍是合法目标。规划在完整同版目录上判断可恢复性，留存口径可彼此重叠或涉及目标外工段。只有当留存覆盖的精确关系能还原完整目标时才发布。执行结束后按净行数决定班组是否出行，按净非空计数区分空金额和整数净额。`StoredReport.header` 提供编号、原修订及排序后的目标工段，`StoredReport.rows` 提供按班组标识排序的账项。`read` 从已提交记录按号读回。更正及归档重开后旧编号仍对应原报告。

## 状态和错误

- 非法复合身份、源行、覆盖、目标和业务日期为 `ValueError` 类错误。非法源行抛出 `InvalidIntake`，非法覆盖抛出 `InvalidCoverage`，非法目标抛出 `InvalidTarget`。未知修订抛出 `UnknownRevision`，冻结覆写抛出 `FrozenRevision`，要求冻结时收到草稿抛出 `RevisionNotFrozen`。
- 提前清理抛出 `NotDue`，留存目录或载荷不完整时清理抛出 `RetentionUnavailable`。所有清理拒绝保留源账。
- 合法目标证据不足抛出 `UnrecoverableTarget`。留存载荷不完整或净统计量非法时，补报分别抛出 `IncompleteRollup` 或 `InvalidMeasures`。SQLite 报告交易失败抛出 `PublicationError`，原 SQLite 异常保留为原因。未知报告号抛出 `ReportNotFound`。
- 归档入口管理自己的事务，调用时连接须未开启事务。写入失败回滚本次交易。`open_archive` 开启连接并执行初始化，调用者负责关闭。也可对已有空闲连接调用 `reports.archive.initialize_archive` 以启用外键并重复初始化，原数据和用户提交的更正会保留。

## 回归

`tests/test_freeze.py` 核对整批校验、留存口径及原子冻结。`tests/test_retention.py` 核对期限边界、重复清理和修订隔离。`tests/test_reissue.py` 用手算结果和独立源账对照互斥、重叠、抵消以及证据不足。`tests/test_reports.py` 用实际 SQLite 写失败核对回滚，并验证更正后的固定编号、整数精度和重开读回。业务日期及数据均固定。
