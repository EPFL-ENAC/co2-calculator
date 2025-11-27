# ADR-013: Object Storage Strategy

**Status**: Planned  
**Date**: 2025-11-10  
**Deciders**: Development Team  
**Related**: [Tech Stack](../architecture/08-tech-stack.md#backend-stack)

## Context

We need a solution for storing user-uploaded files (CSV imports,
reports, exports). The system must scale from local development to
production while remaining cost-effective and maintainable.

This ADR establishes a two-tier approach: local filesystem storage
for development and small deployments, with an optional migration
path to S3-compatible object storage for production scalability.

## Decision

Use **local filesystem storage** as the default implementation.
Adopt **S3-compatible object storage** only when production needs
require it (multi-instance deployments, high availability).

Start with filesystem storage in `/app/data/uploads/`. Add S3
support later through an abstraction layer when actual usage
patterns justify the additional complexity.

## Why Local Filesystem First

- No external dependencies or configuration
- Standard file I/O operations (easy debugging)
- Zero storage costs for small deployments
- Fast development cycles without API latency
- Works offline and in air-gapped environments
- Simple backups with standard tools (rsync, tar)

## Why S3 Later (When Needed)

- Unlimited storage that scales automatically
- Built-in redundancy (99.999999999% durability)
- Direct browser uploads via presigned URLs
- Pay-as-you-go pricing with storage tiers
- Easy CDN integration for faster delivery
- Industry-standard APIs and tooling

## Alternatives Rejected

### Database BLOB Storage

Rejected due to poor performance with large files, database bloat,
and backup complexity. Transactional consistency is not critical
for file uploads.

### Network File Systems (NFS/CIFS)

Rejected due to complex Kubernetes setup, concurrent access
bottlenecks, and horizontal scaling difficulties. Object storage
provides better cloud-native scalability.

## Trade-offs

### Local Filesystem Limitations

- Cannot run multiple backend instances without shared volumes
- No built-in redundancy or automatic backups
- Limited to single-host storage capacity
- Manual retention policy enforcement
- No presigned URL support

### S3 Complexity (When Adopted)

- Lifecycle management and cleanup logic required
- Potential egress costs for downloads
- Network-related error handling needed
- External service dependency
- Team learning curve for S3 APIs

## Implementation

### Current Setup (Local Filesystem)

Store files in `/app/data/uploads/` with this structure:

```
/app/data/uploads/
├── csv/
├── reports/
└── exports/
```

Name files consistently: `{timestamp}_{user_id}_{original_name}`

Store metadata (path, size, mime-type) in the database.

### Upload Flow

1. Backend receives file via multipart/form-data
2. Validate file type (whitelist) and size (configurable limits)
3. Save to filesystem with generated name
4. Store metadata in database

### Security

- Whitelist allowed file extensions
- Enforce size limits per file type
- Use user-specific directories
- Run cleanup jobs for expired files
- Soft-delete with grace period

### Migration to S3 (Future)

When production requires S3:

1. Add storage abstraction layer in backend
2. Configure S3 bucket with environment-based paths
3. Implement presigned URL generation
4. Set up IAM roles with least privilege
5. Enable server-side encryption
6. Configure lifecycle policies for cost optimization

Keep database metadata identical to simplify migration.

## Key Takeaway

Start simple with filesystem storage. Add S3 complexity only when
multi-instance deployments or high availability requirements
emerge. The abstraction layer ensures smooth migration when needed.

## Related Decisions

- [ADR-003: Backend Framework](./003-backend-framework.md) -
  FastAPI supports async file I/O
- [ADR-010: Background Jobs](./010-background-job-processing.md) -
  Cleanup tasks use background jobs

## References

- [AWS S3 Documentation](https://docs.aws.amazon.com/s3/)
- [Presigned URLs](https://docs.aws.amazon.com/AmazonS3/latest/userguide/ShareObjectPreSignedURL.html)
