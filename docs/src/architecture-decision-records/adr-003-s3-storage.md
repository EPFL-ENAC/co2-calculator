# ADR-003: Store Files on S3-compatible Object Storage

## Status

Accepted

## Context

We needed a solution for storing and managing file uploads in our system that would:

- Provide scalable storage for unstructured data
- Offer high availability and durability
- Integrate well with our cloud deployment strategy
- Support direct uploads from browsers to reduce backend load
- Provide fine-grained access control
- Be cost-effective for our expected usage patterns

## Decision

We will use S3-compatible object storage for all file storage needs.

## Rationale

Object storage (specifically S3-compatible) is the ideal solution for our file storage requirements:

1. **Scalability**: Virtually unlimited storage capacity that automatically scales with demand
2. **Durability**: Built-in redundancy and durability (99.999999999% for AWS S3)
3. **Cost-Effectiveness**: Pay-as-you-go pricing model with multiple storage classes
4. **Direct Browser Uploads**: Presigned URLs enable secure direct uploads from browsers
5. **Rich Ecosystem**: Extensive tooling and SDKs for all major programming languages
6. **Industry Standard**: Widely adopted solution with extensive documentation and community support
7. **Access Control**: Fine-grained access control through IAM policies and presigned URLs

Compared to alternatives:

- Storing files in the database would be inefficient and costly
- Storing files on local disk would limit scalability and availability
- Other cloud storage solutions lack the maturity and tooling of S3

## Consequences

### Positive

- Highly scalable storage solution that grows with our needs
- Reduced backend load through direct browser uploads
- Cost-effective storage with multiple pricing tiers
- High availability and durability of stored files
- Easy integration with CDNs for improved delivery performance

### Negative

- Additional complexity in managing file lifecycle and cleanup
- Potential egress costs for file downloads
- Dependency on external storage service
- Need for proper error handling for network-related issues

## Implementation Details

Our S3 implementation will include:

1. **Storage Structure**:

   - Bucket organization by environment (dev, staging, prod)
   - Path-based organization for different file types
   - Consistent naming conventions for objects

2. **Upload Process**:

   - Backend generates presigned URLs for secure uploads
   - Frontend uploads directly to storage using presigned URLs
   - Metadata stored in database with object keys

3. **Security Measures**:

   - IAM roles with least privilege principle
   - Presigned URLs with limited validity period
   - Server-side encryption for all objects
   - Access logging for audit purposes

4. **Lifecycle Management**:
   - Automated transition to cheaper storage classes
   - Deletion policies for temporary files
   - Backup strategies for critical data

## References

- [AWS S3 Documentation](https://docs.aws.amazon.com/s3/)
- [S3 API Reference](https://docs.aws.amazon.com/AmazonS3/latest/API/)
- [Presigned URLs Documentation](https://docs.aws.amazon.com/AmazonS3/latest/userguide/ShareObjectPreSignedURL.html)
