# neos-filed

Neos 的场地图资源仓库。原始素材来自 [ygopro-images-field](https://code.moenext.com/mycard/ygopro-images-field)，此仓库保存转换后的 WebP、可用卡号和上游提交，主项目通过 Git submodule 固定资源版本。

## 自动同步

GitHub Actions 每天在 UTC 03:45（北京时间 11:45）检查上游，也可在 [Sync field artwork](https://github.com/hexzhou/neos-filed/actions/workflows/sync-field-artwork.yml) 页面手动运行并指定上游分支或提交。转换脚本和测试修改后也会运行同步。

CI 拉取上游 `master` 的 `field/`，用 `cwebp -q 85 -m 6` 转换数字卡号图片。所有图片转换成功后，才替换 WebP、清单和来源信息；上游删除的图片同步移除。没有内容变化时不创建提交。CI 使用 GitHub 提供的 `GITHUB_TOKEN` 提交，仅授予当前仓库的写入权限，无需设置个人令牌。

发布目录为 `public/neos-assets/fields/`：

- `<卡号>.webp`：场地图。
- `manifest.json`：按卡号排序的可用图片清单。
- `source.json`：上游地址、提交、数量、转换器版本和参数。

## 本地转换

需要 Python 3.10 以上、Git 和 `cwebp`。macOS 可以安装 `brew install webp`，Debian/Ubuntu 可以安装 `apt-get install git webp`。

```sh
python3 -m unittest discover -s tests -v
python3 scripts/sync-field-artwork.py
# 指定上游版本
python3 scripts/sync-field-artwork.py --revision <上游提交>
# 使用已下载的原图，revision 用于记录来源
python3 scripts/sync-field-artwork.py /path/to/field --revision <上游提交>
```

## 在 Neos 中更新依赖

首次初始化与更新资源是两个操作。初始化会检出主项目已经固定的提交；更新会采用本仓库的最新 `main`，需要把新的子模块提交指针纳入主项目提交。

```sh
# 在 neos-ts 根目录初始化
git submodule update --init -- neos-filed
# 更新到最新资源
git submodule update --init --remote -- neos-filed
git add neos-filed
git commit -m "chore: update field artwork"
```

Neos 的 Vite `publicDir` 指向 `neos-filed/public`，开发和生产构建均使用 `/neos-assets/fields/<卡号>.webp`。前端清单直接从同一子模块导入，避免清单和图片分别更新。
