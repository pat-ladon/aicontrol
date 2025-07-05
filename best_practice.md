# Best Practice Control Assessment Framework

## 1. Control Objective

_A clear, one-sentence statement describing the primary goal of the control._
**Example:** To ensure that access to sensitive data is granted on a need-to-know basis and is promptly revoked when no longer required.

## 2. Risk Mitigated

_A description of the specific risk the control is designed to prevent or reduce._
**Example:** This control mitigates the risk of data breaches caused by former employees or users with excessive standing privileges.

## 3. Mitigation Mechanism

_A detailed explanation of HOW the control works. Describe the people, processes, and technology involved._
**Example:** The control is executed through a semi-automated process where the Identity Management System generates a quarterly report of all users with 'administrator' or 'database_readwrite' roles. This report is automatically assigned to the designated system owner for review. The owner must approve or reject each access right. Rejected rights trigger an automated de-provisioning workflow in the system.

## 4. Evidence of Operation

_Description of the artifacts that prove the control is working._
**Example:** Evidence includes the quarterly access review reports with the system owner's digital signature and timestamp, and system logs showing the de-provisioning of rejected access rights.

## 5. Key Performance Indicators (KPIs)

_Metrics to measure the control's effectiveness._
**Example:**

- Percentage of access reviews completed on time (>99%).
- Time to revoke access after rejection (< 8 business hours).
