"""Yazılım ve elektrik-elektronik ilanlarında görülen beceriler (Kariyer.net örneklemi, Kasım 2026).

Metinler ilanlardan kopyalanmadı; aynı becerileri içeren kısa, uydurma cümlelerdir.
"""

import pytest

from app.services.job_text_analysis_service import analyze_job_text
from app.services.skill_catalog_service import seed_skill_catalog


def skill_names(db_session, text):
    seed_skill_catalog(db_session)
    return {skill["name"] for skill in analyze_job_text(db_session, user_id=1, text=text)["skills"]}


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "C++ ve Qt Framework ile Linux üzerinde geliştirme; CMake, GoogleTest; TCP/IP, UDP ve Modbus haberleşmesi; "
            "CUDA ve TensorRT ile NVIDIA Jetson ve Raspberry Pi platformları; veri yapıları ve algoritmalar",
            {"C++", "Qt", "Linux", "CMake", "GoogleTest", "TCP/IP", "UDP", "Modbus", "CUDA", "TensorRT",
             "NVIDIA Jetson", "Raspberry Pi", "Data Structures and Algorithms"},
        ),
        (
            "C#, .NET Core, ASP.NET MVC, Entity Framework Core ve LINQ; CQRS, SOLID prensipleri, Clean Architecture, "
            "mikroservis mimarisi; Keycloak, OpenID Connect, SSO ve RBAC; Agile ve Scrum; KVKK ve GDPR",
            {"C#", ".NET", "ASP.NET MVC", "Entity Framework Core", "LINQ", "CQRS", "SOLID Principles",
             "Clean Architecture", "Microservices", "Keycloak", "OpenID Connect", "Single Sign-On",
             "Role-Based Access Control", "Agile", "Scrum", "KVKK", "GDPR"},
        ),
        (
            "Azure App Service, AKS, Cosmos DB, Azure Service Bus, Azure DevOps, Key Vault ve Application Insights; "
            "GitHub Copilot; WebSocket ve WebGL",
            {"Azure App Service", "Azure Kubernetes Service", "Azure Cosmos DB", "Azure Service Bus", "Azure DevOps",
             "Azure Key Vault", "Application Insights", "GitHub Copilot", "WebSocket", "WebGL"},
        ),
        (
            "CBS projelerinde OpenLayers veya Leaflet ile harita uygulamaları; GeoServer, ArcGIS, QGIS, GDAL; "
            "SOAP ve WCF web servisleri; CesiumJS ve Mapbox",
            {"GIS", "OpenLayers", "Leaflet", "GeoServer", "ArcGIS", "QGIS", "GDAL", "SOAP", "WCF", "CesiumJS", "Mapbox"},
        ),
        (
            "Gömülü sistemler ve mikrodenetleyiciler; STM32, ESP32; FreeRTOS, Zephyr RTOS; Embedded Linux ve Yocto; "
            "UART, SPI, I2C, CAN ve RS-485 protokolleri; osiloskop ve lojik analizör",
            {"Embedded Systems", "Microcontrollers", "STM32", "ESP32", "FreeRTOS", "Zephyr RTOS", "Embedded Linux",
             "Yocto", "UART", "SPI", "I2C", "CAN Bus", "RS-485", "Oscilloscope", "Logic Analyzer"},
        ),
        (
            "FPGA üzerinde VHDL, Verilog veya SystemVerilog ile RTL tasarım ve simülasyon; Vivado",
            {"FPGA", "VHDL", "Verilog", "SystemVerilog", "RTL Design", "Vivado"},
        ),
        (
            "PCB kart tasarımı, PLC programlama, yalın üretim ve kök neden analizi",
            {"PCB Design", "PLC", "Lean Manufacturing", "Root Cause Analysis"},
        ),
        (
            "Test otomasyonu için Selenium ve Appium; regresyon testleri, entegrasyon testleri, kullanıcı kabul testleri; "
            "TDD; Jira ve HP Quality Center; SVN ve TFS; Android NDK ve JNI",
            {"Test Automation", "Selenium", "Appium", "Regression Testing", "Integration Testing",
             "User Acceptance Testing", "Test-Driven Development", "Jira", "HP ALM", "SVN", "Team Foundation Server",
             "Android NDK", "JNI"},
        ),
    ],
    ids=["cpp-gorsel", "dotnet-fullstack", "azure", "cbs", "gomulu", "fpga", "uretim", "test-ve-mobil"],
)
def test_engineering_posting_skills_are_extracted(db_session, text, expected):
    assert expected <= skill_names(db_session, text)


@pytest.mark.parametrize(
    ("text", "unexpected"),
    [
        ("Görüşmeleri İK'dan Can Bey yürütecek; adaylar we can talk diyebilir.", "CAN Bus"),
        ("Solid bir iş deneyimi ve güçlü iletişim arıyoruz.", "SOLID Principles"),
        ("Soap ve şampuan üretim hattında kalite kontrol.", "SOAP"),
        ("Fuarda leaflet ve broşür dağıtımı yapılacak.", "Leaflet"),
        ("RTL Group yayın kuruluşunda medya planlama.", "RTL Design"),
        ("Otomotiv yan sanayide aks montajı ve kalite kontrol.", "Azure Kubernetes Service"),
        ("Müşteri Qt adetlerini sipariş formuna girecek.", "Qt"),
    ],
    ids=["can", "solid", "soap", "leaflet", "rtl", "aks", "qt"],
)
def test_ambiguous_words_need_technical_context(db_session, text, unexpected):
    assert unexpected not in skill_names(db_session, text)
