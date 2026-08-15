# Feature Requests

Capabilities requested by the user.

---

## [FEAT-20260814-001] yolo-annotation-preview

**Logged**: 2026-08-14T00:00:00+08:00
**Priority**: medium
**Status**: in_progress
**Area**: frontend

### Requested Capability
Allow a user to enter an image-folder path and matching label-folder path, select an image, and preview the image with YOLO bounding boxes drawn by the backend. Show numeric class IDs by default; when the user supplies ID-to-name mappings, show the corresponding text class names.

### User Context
The feature is intended for visually inspecting object-detection annotations and resolving numeric class IDs into readable category names.

### Complexity Estimate
medium

### Suggested Implementation
Add backend endpoints for safe image enumeration and rendered annotation previews, then add a frontend panel with path inputs, image selection/navigation, ID:name mapping input, validation, and in-page preview.

### Metadata
- Frequency: first_time
- Related Features: dataset_analysis, label_extraction, dataset_integrity_check

---
